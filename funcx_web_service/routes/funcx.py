import json
import time
import uuid
import requests

from flask import current_app as app, Blueprint, jsonify, request, g

from funcx_web_service.authentication.auth import authenticated_w_uuid
from funcx_web_service.authentication.auth import authorize_endpoint, authenticated, authorize_function

from funcx_web_service.models.tasks import Task
from funcx_web_service.models.utils import get_redis_client, \
    ingest_endpoint
from funcx_web_service.models.utils import register_endpoint, ingest_function
from funcx_web_service.models.utils import resolve_function, db_invocation_logger
from funcx_web_service.models.utils import (update_function, delete_function, get_ep_whitelist,
                                            add_ep_whitelist, delete_ep_whitelist)
from funcx_web_service.error_responses import create_error_response
from funcx_web_service.version import VERSION

from funcx_forwarder.queues.redis.redis_pubsub import RedisPubSub
from .redis_q import EndpointQueue

from funcx.utils.response_errors import (UserNotFound, ContainerNotFound, TaskNotFound,
                                         AuthGroupNotFound, FunctionAccessForbidden, EndpointAccessForbidden,
                                         ForwarderRegistrationError, ForwarderContactError, EndpointStatsError,
                                         LivenessStatsError, RequestKeyError, RequestMalformed, InternalError,
                                         EndpointOutdated)
from funcx.sdk.version import VERSION as FUNCX_VERSION

# Flask
from ..models.auth_groups import AuthGroup
from ..models.container import Container, ContainerImage
from ..models.endpoint import Endpoint
from ..models.function import Function, FunctionContainer, FunctionAuthGroup
from ..models.serializer import serialize_inputs, deserialize_result
from ..models.user import User

funcx_api = Blueprint("routes", __name__)


def get_db_logger():
    if 'db_logger' not in g:
        g.db_logger = db_invocation_logger()
    return g.db_logger


def g_redis_client():
    if 'redis_client' not in g:
        g.redis_client = get_redis_client()
    return g.redis_client


def g_redis_pubsub(*args, **kwargs):
    if 'redis_pubsub' not in g:
        g.redis_pubsub = RedisPubSub(*args, **kwargs)
        g.redis_pubsub.connect()
        rc = g.redis_pubsub.redis_client
        rc.ping()
    return g.redis_pubsub


def auth_and_launch(user_id, function_uuid, endpoint_uuid, input_data, app, token, serialize=None):
    """ Here we do basic auth for (user, fn, endpoint) and launch the function.

    Parameters
    ==========

    user_id : str
       user id
    function_uuid : str
       function uuid
    endpoint_uuid : str
       endpoint uuid
    input_data : string_buffer
       input payload data
    app : app object
    token : globus token
    serialize : bool
        Whether or not to serialize the input using the serialization service. This is used
        when the input is not already serialized by the SDK.

    Returns:
       JSON response object, containing task_uuid, http_status_code, and success or error info
    """
    task_uuid = str(uuid.uuid4())
    # Check if the user is allowed to access the function
    try:
        if not authorize_function(user_id, function_uuid, token):
            res = create_error_response(FunctionAccessForbidden(function_uuid))[0]
            res['task_uuid'] = task_uuid
            return res
    except Exception as e:
        # could be FunctionNotFound
        res = create_error_response(e)[0]
        res['task_uuid'] = task_uuid
        return res

    try:
        fn_code, fn_entry, container_uuid = resolve_function(user_id, function_uuid)
    except Exception as e:
        # could be FunctionNotFound
        res = create_error_response(e)[0]
        res['task_uuid'] = task_uuid
        return res

    # Make sure the user is allowed to use the function on this endpoint
    try:
        if not authorize_endpoint(user_id, endpoint_uuid, function_uuid, token):
            res = create_error_response(EndpointAccessForbidden(endpoint_uuid))[0]
            res['task_uuid'] = task_uuid
            return res
    except Exception as e:
        # could be an EndpointNotFound or a FunctionNotPermitted
        res = create_error_response(e)[0]
        res['task_uuid'] = task_uuid
        return res

    app.logger.debug(f"Got function container_uuid :{container_uuid}")

    # We should replace this with container_hdr = ";ctnr={container_uuid}"
    if not container_uuid:
        container_uuid = 'RAW'

    # We should replace this with serialize_hdr = ";srlz={container_uuid}"
    # TODO: this is deprecated.
    serializer = "ANY"

    rc = g_redis_client()
    task_channel = g_redis_pubsub(app.config['REDIS_HOST'],
                                  port=app.config['REDIS_PORT'])

    db_logger = get_db_logger()
    ep_queue = {}

    redis_task_queue = EndpointQueue(
        endpoint_uuid,
        hostname=app.config['REDIS_HOST'],
        port=app.config['REDIS_PORT']
    )
    redis_task_queue.connect()
    ep_queue[endpoint_uuid] = redis_task_queue

    if serialize:
        serialize_res = serialize_inputs(input_data)
        if serialize_res:
            input_data = serialize_res

    # At this point the packed function body and the args are concatable strings
    payload = fn_code + input_data
    task = Task(rc, task_uuid, container_uuid, serializer, payload)

    task_channel.put(endpoint_uuid, task)
    app.logger.debug(f"Task:{task_uuid} placed on queue for endpoint:{endpoint_uuid}")

    # increment the counter
    rc.incr('funcx_invocation_counter')
    # add an invocation to the database
    # log_invocation(user_id, task_uuid, function_uuid, ep)
    db_logger.log(user_id, task_uuid, function_uuid, endpoint_uuid, deferred=True)

    db_logger.commit()

    return {'status': 'Success',
            'task_uuid': task_uuid,
            'http_status_code': 200}


@funcx_api.route('/submit', methods=['POST'])
@authenticated
def submit(user: User):
    """Puts the task request(s) into Redis and returns a list of task UUID(s)
    Parameters
    ----------
    user : User
    The primary identity of the user

    POST payload
    ------------
    {
        tasks: []
    }
    Returns
    -------
    json
        The task document
    """

    app.logger.debug(f"batch_run invoked by user:{user.username}")

    user_id = user.id

    # Extract the token for endpoint verification
    token_str = request.headers.get('Authorization')
    token = str.replace(str(token_str), 'Bearer ', '')

    # Parse out the function info
    tasks = []
    try:
        post_req = request.json
        if 'tasks' in post_req:
            # new client is being used
            tasks = post_req['tasks']
        else:
            # old client was used and create a new task
            function_uuid = post_req['func']
            endpoint = post_req['endpoint']
            input_data = post_req['payload']
            tasks.append([function_uuid, endpoint, input_data])
        serialize = post_req.get('serialize', None)
    except KeyError as e:
        # this should raise a 500 because it prevented any tasks from launching
        return create_error_response(RequestKeyError(e), jsonify_response=True)

    # this is a breaking change for old funcx sdk versions
    results = {'response': 'batch',
               'results': []}

    final_http_status = 200
    for task in tasks:
        res = auth_and_launch(
            user_id, function_uuid=task[0], endpoint_uuid=task[1],
            input_data=task[2], app=app, token=token, serialize=serialize
        )
        # the response code is a 207 if some tasks failed to submit
        if res.get('status', 'Failed') != 'Success':
            final_http_status = 207

        results['results'].append(res)
    return jsonify(results), final_http_status


def get_tasks_from_redis(task_ids):
    all_tasks = {}

    rc = g_redis_client()
    for task_id in task_ids:
        # Get the task from redis
        if not Task.exists(rc, task_id):
            all_tasks[task_id] = {
                'status': 'Failed',
                'reason': 'Unknown task id'
            }
            continue

        task = Task.from_id(rc, task_id)
        task_status = task.status
        task_result = task.result
        task_exception = task.exception
        task_completion_t = task.completion_time
        if task_result or task_exception:
            task.delete()

        all_tasks[task_id] = {
            'task_id': task_id,
            'status': task_status,
            'result': task_result,
            'completion_t': task_completion_t,
            'exception': task_exception
        }

        # Note: this is for backwards compat, when we can't include a None result and have a
        # non-complete status, we must forgo the result field if task not complete.
        if task_result is None:
            del all_tasks[task_id]['result']

        # Note: this is for backwards compat, when we can't include a None result and have a
        # non-complete status, we must forgo the result field if task not complete.
        if task_exception is None:
            del all_tasks[task_id]['exception']
    return all_tasks


# TODO: Old APIs look at "/<task_id>/status" for status and result, when that's changed, we should remove this route
@funcx_api.route("/<task_id>/status", methods=['GET'])
@funcx_api.route("/tasks/<task_id>", methods=['GET'])
@authenticated
def status_and_result(user_name, task_id):
    """Check the status of a task.  Return result if available.

    If the query param deserialize=True is passed, then we deserialize the result object.

    Parameters
    ----------
    user_name : str
        The primary identity of the user
    task_id : str
        The task uuid to look up

    Returns
    -------
    json
        The status of the task
    """
    rc = g_redis_client()

    if not Task.exists(rc, task_id):
        return create_error_response(TaskNotFound(task_id), jsonify_response=True)

    task = Task.from_id(rc, task_id)
    task_status = task.status
    task_result = task.result
    task_exception = task.exception
    task_completion_t = task.completion_time
    if task_result or task_exception:
        task.delete()

    deserialize = request.args.get("deserialize", False)
    if deserialize and task_result:
        task_result = deserialize_result(task_result)

    # TODO: change client to have better naming conventions
    # these fields like 'status' should be changed to 'task_status', because 'status' is normally
    # used for HTTP codes.
    response = {
        'task_id': task_id,
        'status': task_status,
        'result': task_result,
        'completion_t': task_completion_t,
        'exception': task_exception
    }

    # Note: this is for backwards compat, when we can't include a None result and have a
    # non-complete status, we must forgo the result field if task not complete.
    if task_result is None:
        del response['result']

    if task_exception is None:
        del response['exception']

    return jsonify(response)


@funcx_api.route("/batch_status", methods=['POST'])
@authenticated
def batch_status(user: User):
    """Check the status of a task.

    Parameters
    ----------
    user : User
        The primary identity of the user
    task_id : str
        The task uuid to look up

    Returns
    -------
    json
        The status of the task
    """
    app.logger.debug("request : {}".format(request.json))
    results = get_tasks_from_redis(request.json['task_ids'])

    return jsonify({'response': 'batch',
                    'results': results})


@funcx_api.route("/containers/<container_id>/<container_type>", methods=['GET'])
@authenticated
def get_cont(user: User, container_id, container_type):
    """Get the details of a container.

    Parameters
    ----------
    user : User
        The primary identity of the user
    container_id : str
        The id of the container
    container_type : str
        The type of containers to return: Docker, Singularity, Shifter, etc.

    Returns
    -------
    dict
        A dictionary of container details
    """

    app.logger.debug(f"Getting container details: {container_id}")
    container = Container.find_by_uuid_and_type(container_id, container_type)
    app.logger.debug(f"Got container: {container}")
    return jsonify({'container': container.to_json()})


@funcx_api.route("/containers", methods=['POST'])
@authenticated
def reg_container(user: User):
    """Register a new container.

    Parameters
    ----------
    user : User
        The primary identity of the user

    JSON Body
    ---------
        name: Str
        description: Str
        type: The type of containers that will be used (Singularity, Shifter, Docker)
        location:  The location of the container (e.g., its docker url).

    Returns
    -------
    dict
        A dictionary of container details including its uuid
    """

    app.logger.debug("Creating container.")
    post_req = request.json

    try:
        container_rec = Container(
            author=user.id,
            name=post_req['name'],
            description=None if not post_req['description'] else post_req['description'],
            container_uuid=str(uuid.uuid4())
        )
        container_rec.images = [
            ContainerImage(
                type=post_req['type'],
                location=post_req['location']
            )
        ]

        container_rec.save_to_db()

        app.logger.debug(f"Created container: {container_rec.container_uuid}")
        return jsonify({'container_id': container_rec.container_uuid})
    except KeyError as e:
        return create_error_response(RequestKeyError(e), jsonify_response=True)

    except Exception as e:
        return create_error_response(InternalError(f'error adding container - {e}'), jsonify_response=True)


def register_with_hub(address, endpoint_id, endpoint_address):
    """ This registers with the Forwarder micro service.

    Can be used as an example of how to make calls this it, while the main API
    is updated to do this calling on behalf of the endpoint in the second iteration.

    Parameters
    ----------
    address : str
       Address of the forwarder service of the form http://<IP_Address>:<Port>

    """
    print(address + '/register')
    r = requests.post(address + '/register',
                      json={'endpoint_id': endpoint_id,
                            'redis_address': app.config['ADVERTISED_REDIS_HOST'],
                            'endpoint_addr': endpoint_address,
                            }
                      )
    if r.status_code != 200:
        print(dir(r))
        print(r)
        raise ForwarderRegistrationError(r.reason)

    return r.json()


def get_forwarder_version():
    forwarder_ip = app.config['FORWARDER_IP']
    r = requests.get(f"http://{forwarder_ip}:8080/version")
    return r.json()


@funcx_api.route("/version", methods=['GET'])
def get_version():
    s = request.args.get("service")
    if s == "api" or s is None:
        return jsonify(VERSION)
    elif s == "funcx":
        return jsonify(FUNCX_VERSION)

    forwarder_v_info = get_forwarder_version()
    forwarder_version = forwarder_v_info['forwarder']
    min_ep_version = forwarder_v_info['min_ep_version']
    if s == 'forwarder':
        return jsonify(forwarder_version)

    if s == 'all':
        return jsonify({
            "api": VERSION,
            "funcx": FUNCX_VERSION,
            "forwarder": forwarder_version,
            "min_ep_version": min_ep_version
        })

    return create_error_response(RequestMalformed("unknown service type or other error."), jsonify_response=True)


@funcx_api.route("/addr", methods=['GET'])
def get_request_addr():
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return jsonify({'ip': request.environ['REMOTE_ADDR']}), 200
    else:
        return jsonify({'ip': request.environ['HTTP_X_FORWARDED_FOR']}), 200


# Endpoint routes
@funcx_api.route("/endpoints", methods=['POST'])
@authenticated_w_uuid
def reg_endpoint(user: User, user_uuid: str):
    """Register an endpoint. Add this endpoint to the database and associate it with this user.

    Returns
    -------
    json
        A dict containing the endpoint details
    """
    app.logger.debug("register_endpoint triggered")
    app.logger.debug(request.json)

    v_info = get_forwarder_version()
    min_ep_version = v_info['min_ep_version']
    if 'version' not in request.json:
        return create_error_response(RequestKeyError("Endpoint funcx version must be passed in the 'version' field."), jsonify_response=True)

    if request.json['version'] < min_ep_version:
        return create_error_response(EndpointOutdated(min_ep_version), jsonify_response=True)

    # Cooley ALCF is the default used here.
    endpoint_ip_addr = '140.221.68.108'
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        endpoint_ip_addr = request.environ['REMOTE_ADDR']
    else:
        endpoint_ip_addr = request.environ['HTTP_X_FORWARDED_FOR']
    app.logger.debug(f"Registering endpoint IP address as: {endpoint_ip_addr}")

    # always return the jsonified error response as soon as it is available below
    # to prevent further registration steps being taken after an error
    try:
        app.logger.debug(request.json['endpoint_name'])
        app.logger.debug(f"requesting registration for {request.json}")
        endpoint_uuid = register_endpoint(user,
                                          request.json['endpoint_name'],
                                          "",  # use description from meta? why store here at all
                                          endpoint_uuid=request.json['endpoint_uuid'])
        app.logger.debug(f"Successfully registered {endpoint_uuid} in database")

    except KeyError as e:
        app.logger.exception("Missing keys in json request")
        return create_error_response(RequestKeyError(e), jsonify_response=True)

    except UserNotFound as e:
        app.logger.exception("User not found")
        return create_error_response(e, jsonify_response=True)

    except Exception as e:
        app.logger.exception("Caught error while registering endpoint")
        return create_error_response(e, jsonify_response=True)

    try:
        forwarder_ip = app.config['FORWARDER_IP']
        response = register_with_hub(
                f"http://{forwarder_ip}:8080", endpoint_uuid, endpoint_ip_addr)
        app.logger.debug(f"Successfully registered {endpoint_uuid} with forwarder")

    except Exception as e:
        app.logger.exception("Caught error during forwarder initialization")
        return create_error_response(e, jsonify_response=True)

    if 'meta' in request.json and endpoint_uuid:
        ingest_endpoint(user.username, user_uuid, endpoint_uuid, request.json['meta'])
        app.logger.debug(f"Ingested endpoint {endpoint_uuid}")

    try:
        return jsonify(response)
    except NameError:
        return "oof"


@funcx_api.route("/endpoints/<endpoint_id>/status", methods=['GET'])
@authenticated
def get_ep_stats(user: User, endpoint_id):
    """Retrieve the status updates from an endpoint.

    Parameters
    ----------
    user : User
        The primary identity of the user
    endpoint_id : str
        The endpoint uuid to look up

    Returns
    -------
    json
        The status of the endpoint
    """
    alive_threshold = 2 * 60  # time in seconds since last heartbeat to be counted as alive
    last = 10

    user_id = user.id

    # Extract the token for endpoint verification
    token_str = request.headers.get('Authorization')
    token = str.replace(str(token_str), 'Bearer ', '')

    try:
        if not authorize_endpoint(user_id, endpoint_id, None, token):
            return create_error_response(EndpointAccessForbidden(endpoint_id), jsonify_response=True)
    except Exception as e:
        # could be EndpointNotFound
        return create_error_response(e, jsonify_response=True)

    rc = g_redis_client()

    status = {'status': 'offline', 'logs': []}
    try:
        end = min(rc.llen(f'ep_status_{endpoint_id}'), last)
        print("Total len :", end)
        items = rc.lrange(f'ep_status_{endpoint_id}', 0, end)
        if items:
            for i in items:
                status['logs'].append(json.loads(i))

            # timestamp is created using time.time(), which returns seconds since epoch UTC
            logs = status['logs']  # should have been json loaded already
            newest_timestamp = logs[0]['timestamp']
            now = time.time()
            if now - newest_timestamp < alive_threshold:
                status['status'] = 'online'

    except Exception as e:
        app.logger.error("Unable to retrieve ")
        return create_error_response(EndpointStatsError(endpoint_id, e), jsonify_response=True)

    return jsonify(status)


@funcx_api.route("/endpoints/<endpoint_id>", methods=['DELETE'])
@authenticated
def del_endpoint(user: User, endpoint_id):
    """Delete the endpoint.

        Parameters
        ----------
        user : User
            The primary identity of the user
        endpoint_id : str
            The endpoint uuid to delete

        Returns
        -------
        json
            Dict containing the result
        """
    try:
        result = Endpoint.delete_endpoint(user, endpoint_id)
        return jsonify({'result': result})
    except Exception as e:
        app.logger.error(e)


# Whitelist routes
@funcx_api.route("/endpoints/<endpoint_id>/whitelist", methods=['POST', 'GET'])
@authenticated
def endpoint_whitelist(user: User, endpoint_id):
    """Get or insert into the endpoint's whitelist.
    If POST, insert the list of function ids into the whitelist.
    if GET, return the list of function ids in the whitelist

    Parameters
    ----------
    user : User
        The primary identity of the user
    endpoint_id : str
        The id of the endpoint

    Returns
    -------
    json
        A dict including a list of whitelisted functions for this endpoint
    """

    app.logger.debug(f"Adding to endpoint {endpoint_id} whitelist by user: {user.username}")

    if request.method == "GET":
        return get_ep_whitelist(user, endpoint_id)
    else:
        # Otherwise we need the list of functions passed in
        try:
            post_req = request.json
            functions = post_req['func']
        except KeyError as e:
            return create_error_response(RequestKeyError(e), jsonify_response=True)
        except Exception as e:
            return create_error_response(RequestMalformed(e), jsonify_response=True)
        return add_ep_whitelist(user, endpoint_id, functions)


@funcx_api.route("/endpoints/<endpoint_id>/whitelist/<function_id>", methods=['DELETE'])
@authenticated
def del_endpoint_whitelist(user: User, endpoint_id, function_id):
    """Delete from an endpoint's whitelist. Return the success/failure of the delete.

    Parameters
    ----------
    user : User
        The primary identity of the user
    endpoint_id : str
        The id of the endpoint
    function_id : str
        The id of the function to delete

    Returns
    -------
    json
        A dict describing the result of deleting from the endpoint's whitelist
    """

    app.logger.debug(f"Deleting function {function_id} from endpoint {endpoint_id} whitelist by user: {user.username}")

    return delete_ep_whitelist(user, endpoint_id, function_id)


@funcx_api.route("/functions", methods=['POST'])
@authenticated_w_uuid
def reg_function(user: User, user_uuid):
    """Register the function.

    Parameters
    ----------
    user : str
        The primary identity of the user

    POST Payload
    ------------
    { "function_name" : <FN_NAME>,
      "entry_point" : <ENTRY_POINT>,
      "function_code" : <ENCODED_FUNCTION_BODY>,
      "function_source": <UNENCODED FUNCTION BODY"?
      "container_uuid" : <CONTAINER_UUID>,
      "description" : <DESCRIPTION>,
      "group": <GLOBUS GROUP ID>
      "public" : <BOOL>
      "searchable" : <BOOL>
    }

    Returns
    -------
    json
        Dict containing the function details
    """

    function_rec = None
    function_source = None
    try:
        function_source = request.json["function_source"]
        function_rec = Function(
            function_uuid=str(uuid.uuid4()),
            function_name=request.json["function_name"],
            entry_point=request.json["entry_point"],
            description=request.json["description"],
            function_source_code=request.json["function_code"],
            public=request.json.get("public", False),
            user_id=user.id
        )

        container_uuid = request.json.get("container_uuid", None)
        container = None
        if container_uuid:
            container = Container.find_by_uuid(container_uuid)
            if not container:
                return create_error_response(ContainerNotFound(container_uuid), jsonify_response=True)

        group_uuid = request.json.get("group", None)
        group = None
        if group_uuid:
            group = AuthGroup.find_by_uuid(group_uuid)
            if not group:
                return create_error_response(AuthGroupNotFound(group_uuid), jsonify_response=True)

        searchable = request.json.get("searchable", True)

        app.logger.debug(f"Registering function {function_rec.function_name} "
                         f"with container {container_uuid}")

        if container:
            function_rec.container = FunctionContainer(
                function=function_rec,
                container=container
            )

        if group:
            function_rec.auth_groups = [
                FunctionAuthGroup(
                    group=group,
                    function=function_rec
                )
            ]

        function_rec.save_to_db()

        response = jsonify({'function_uuid': function_rec.function_uuid})

        if not searchable:
            return response

    except KeyError as key_error:
        app.logger.error(key_error)
        return create_error_response(RequestKeyError(key_error), jsonify_response=True)

    except Exception as e:
        message = "Function registration failed for user:{} function_name:{} due to {}".\
            format(user.username, function_rec.function_name, e)
        app.logger.error(message)
        return create_error_response(InternalError(message), jsonify_response=True)

    try:
        ingest_function(function_rec, function_source, user_uuid)
    except Exception as e:
        message = "Function ingest to search failed for user:{} function_name:{} due to {}".\
            format(user.username, function_rec.function_name, e)
        app.logger.error(message)
        return create_error_response(InternalError(message), jsonify_response=True)

    return response


@funcx_api.route("/functions/<function_id>", methods=['PUT'])
@authenticated
def upd_function(user: User, function_id):
    """Update the function.

        Parameters
        ----------
        user : User
            The primary identity of the user
        function_id : str
            The function to update

        Returns
        -------
        json
            Dict containing the result as an integer
        """
    try:
        function_name = request.json["name"]
        function_desc = request.json["desc"]
        function_entry_point = request.json["entry_point"]
        function_code = request.json["code"]
        result = update_function(user.username, function_id, function_name,
                                 function_desc, function_entry_point, function_code)
        if result == 302:
            return jsonify({'function_uuid': function_id}), 302
        elif result == 403:
            message = "Unable to update function for user:{} function_id:{}. 403 Unauthorized".\
                format(user.username, function_id)
            app.logger.error(message)
            return create_error_response(InternalError(message), jsonify_response=True)
        elif result == 404:
            message = "Unable to update function for user:{} function_id:{}. 404 Function not found.".\
                format(user.username, function_id)
            app.logger.error(message)
            return create_error_response(InternalError(message), jsonify_response=True)
    except Exception as e:
        app.logger.error(e)
        message = "Unable to update function for user:{} function_id:{} due to {}".\
            format(user.username, function_id, e)
        app.logger.error(message)
        return create_error_response(InternalError(message), jsonify_response=True)


@funcx_api.route("/functions/<function_id>", methods=['DELETE'])
@authenticated
def del_function(user: User, function_id):
    """Delete the function.

        Parameters
        ----------
        user : User
            The primary identity of the user
        function_id : str
            The function uuid to delete

        Returns
        -------
        json
            Dict containing the result
        """
    try:
        result = delete_function(user, function_id)
        return jsonify({'result': result})
    except Exception as e:
        app.logger.error(e)


@funcx_api.route("/ep_live", methods=['GET'])
def get_stats_from_forwarder(forwarder_address="http://10.0.0.112:8080"):
    """ Get stats from the forwarder
    """
    app.logger.debug("Getting stats from forwarder")
    try:
        r = requests.get(forwarder_address + '/map.json')
        if r.status_code != 200:
            return create_error_response(LivenessStatsError(r.status_code), jsonify_response=True)
        else:
            response = r.json()
            app.logger.debug(f'Response from forwarder : {response}')
            return response

    except Exception as e:
        return create_error_response(ForwarderContactError(e), jsonify_response=True)


@funcx_api.route("/counters/invocations")
def function_count():
    """Get the total number of function invocations.
    """
    app.logger.debug("Getting invocation counter")
    try:
        rc = g_redis_client()
        result = rc.get('funcx_invocation_counter')
        return jsonify({"invocation_count": result}), 200
    except Exception as e:
        app.logger.error(e)
        message = "Unable to get invocation count due to {}".\
            format(e)
        app.logger.error(message)
        return create_error_response(InternalError(message), jsonify_response=True)
