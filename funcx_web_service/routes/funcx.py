import json
import time
import uuid
import requests

from flask import current_app as app, Blueprint, jsonify, request, abort, send_from_directory, g

from funcx_web_service.authentication.auth import authenticated_w_uuid
from funcx_web_service.authentication.auth import authorize_endpoint, authenticated, authorize_function

from funcx_web_service.models.tasks import Task
from funcx_web_service.models.utils import get_redis_client, \
    ingest_endpoint
from funcx_web_service.models.utils import register_endpoint, ingest_function
from funcx_web_service.models.utils import resolve_function, db_invocation_logger
from funcx_web_service.models.utils import (update_function, delete_function, get_ep_whitelist,
                                            add_ep_whitelist, delete_ep_whitelist)
from funcx_web_service.errors import UserNotFound, ForwarderRegistrationError
from funcx_web_service.version import VERSION

from funcx_forwarder.queues.redis.redis_pubsub import RedisPubSub
from .redis_q import EndpointQueue

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


def auth_and_launch(user_id, function_uuid, endpoints, input_data, app, token, serialize=None):
    """ Here we do basic authz for (user, fn, endpoint(s)) and launch the functions

    Parameters
    ==========

    user_id : str
       user id
    function_uuid : str
       uuid string for functions
    endpoints : [str]
       endpoint_uuid as list
    input_data: [string_buffers]
       input_data as a list in case many function launches are to be made
    app : app object
    token : globus token
    serialize : bool
        Whether or not to serialize the input using the serialization service. This is used
        when the input is not already serialized by the SDK.

    Returns:
       json object
    """
    # Check if the user is allowed to access the function
    try:
        if not authorize_function(user_id, function_uuid, token):
            return {'status': 'Failed',
                    'reason': f'Unauthorized access to function: {function_uuid}'}
    except Exception as e:
        print(e)
        return {'status': 'Failed',
                'reason': f'Function authorization failed. {str(e)}'}

    try:
        fn_code, fn_entry, container_uuid = resolve_function(user_id, function_uuid)
    except Exception as e:
        return {'status': 'Failed',
                'reason': f'Function {function_uuid} could not be resolved. {e}'}

    # Make sure the user is allowed to use the function on this endpoint
    for ep in endpoints:
        try:
            if not authorize_endpoint(user_id, ep, function_uuid, token):
                return {'status': 'Failed',
                        'reason': f'Unauthorized access to endpoint: {ep}'}    
        except Exception as e:
            return {'status': 'Failed',
                    'reason': f'Endpoint authorization failed for endpoint {ep}. {e}'}

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

    if isinstance(input_data, list):
        input_data_items = input_data
    else:
        input_data_items = [input_data]

    task_ids = []

    db_logger = get_db_logger()
    ep_queue = {}
    for ep in endpoints:
        redis_task_queue = EndpointQueue(
            ep,
            hostname=app.config['REDIS_HOST'],
            port=app.config['REDIS_PORT']
        )
        redis_task_queue.connect()
        ep_queue[ep] = redis_task_queue

    for input_data in input_data_items:
        if serialize:
            res = serialize_inputs(input_data)
            if res:
                input_data = res

        # At this point the packed function body and the args are concatable strings
        payload = fn_code + input_data
        task_id = str(uuid.uuid4())
        task = Task(rc, task_id, container_uuid, serializer, payload)

        for ep in endpoints:
            task_channel.put(ep, task)
            app.logger.debug(f"Task:{task_id} placed on queue for endpoint:{ep}")

            # increment the counter
            rc.incr('funcx_invocation_counter')
            # add an invocation to the database
            # log_invocation(user_id, task_id, function_uuid, ep)
            db_logger.log(user_id, task_id, function_uuid, ep, deferred=True)

        task_ids.append(task_id)
    db_logger.commit()

    return {'status': 'Success',
            'task_uuids': task_ids}


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
        abort(422, description=f"Missing key: {e}")

    results = {'status': 'Success',
               'task_uuids': [],
               'task_uuid': ""}
    for task in tasks:
        res = auth_and_launch(
            user_id, function_uuid=task[0], endpoints=[task[1]],
            input_data=task[2], app=app, token=token, serialize=serialize
        )
        if res.get('status', 'Failed') != 'Success':
            return res
        else:
            results['task_uuids'].extend(res['task_uuids'])
            # For backwards compatibility. <=0.0.1a5 requires "task_uuid" in result
            # Note: previous versions did not support batching, so returning the first one is ok.
            results['task_uuid'] = res['task_uuids'][0]
    return jsonify(results)


# YADU'S BATCH ROUTE FOR ANNA -- CAN WE DELETE?
# If we delete this we should change auth_and_launch to not accept
# lists for input and endpoints
@funcx_api.route('/submit_batch', methods=['POST'])
@authenticated
def submit_batch(user_name):
    """
    Puts the task request(s) into Redis and returns a list of task UUID(s)
    Parameters
    ----------
    user_name : str
    The primary identity of the user
    POST payload
    ------------
    {
    }
    Returns
    -------
    json
        The task document
    """
    app.logger.debug(f"Submit_batch invoked by user:{user_name}")

    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")

    saved_user = User.resolve_user(user_name)
    if not saved_user:
        msg = f"Failed to resolve user_name:{user_name} to user_id"
        app.logger.error(msg)
        abort(500, description=msg)

    user_id = saved_user.id

    # Extract the token for endpoint verification
    token_str = request.headers.get('Authorization')
    token = str.replace(str(token_str), 'Bearer ', '')

    # Parse out the function info
    try:
        post_req = request.json
        endpoints = post_req['endpoints']
        function_uuid = post_req['func']
        input_data = post_req['payload']
        serialize = post_req.get('serialize', None)
    except KeyError as e:
        return jsonify({'status': 'Failed',
                        'reason': "Missing Key {}".format(str(e))})
    except Exception as e:
        return jsonify({'status': 'Failed',
                        'reason': 'Request Malformed. Missing critical information: {}'.format(str(e))})

    return jsonify(auth_and_launch(user_id,
                                   function_uuid,
                                   endpoints,
                                   input_data,
                                   app,
                                   token,
                                   serialize=serialize))


def get_tasks_from_redis(task_ids):
    all_tasks = {}

    rc = get_redis_client()
    for task_id in task_ids:
        # Get the task from redis
        if not Task.exists(rc, task_id):
            all_tasks[task_id] = {
                'status': 'failed',
                'reason': 'unknown task id'
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
    rc = get_redis_client()

    if not Task.exists(rc, task_id):
        abort(400, "task_id not found")

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


@funcx_api.route("/tasks/<task_id>/status", methods=['GET'])
@authenticated
def status(user_name, task_id):
    """Check the status of a task.

    Parameters
    ----------
    user_name
    task_id

    Returns
    -------
    json
        'status' : task status
    """
    rc = get_redis_client()

    if not Task.exists(rc, task_id):
        abort(400, "task_id not found")
    task = Task.from_id(rc, task_id)

    return jsonify({
        'status': task.status
    })


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


@funcx_api.route("/<task_id>/result", methods=['GET'])
@authenticated
def result(user: User, task_id):
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

    try:
        # Get a redis client
        rc = get_redis_client()

        details = {}

        # Get the task from redis
        try:
            result_obj = rc.hget(f"task_{task_id}", 'result')
            app.logger.debug(f"ResulOBt_obj : {result_obj}")
            if result_obj:
                task = json.loads(result_obj)
            else:
                task = {'status': 'PENDING'}
        except Exception as e:
            app.logger.error(f"Failed to fetch results for {task_id} due to {e}")
            task = {'status': 'FAILED', 'reason': 'Unknown task id'}

        res = {'task_id': task_id}
        if 'status' in task:
            res['status'] = task['status']

        if 'result' in task:
            details['result'] = task['result']
        if 'reason' in task:
            details['reason'] = task['reason']

        if details:
            res.update({'details': details})

        app.logger.debug("Status Response: {}".format(str(res)))
        return jsonify(res)

    except Exception as e:
        app.logger.error(e)
        return jsonify({'status': 'Failed',
                        'reason': 'InternalError: {}'.format(e)})


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
        abort(400, f"Missing property in request: {e}")

    except Exception as e:
        abort(500, f'Internal server error adding container {e}')


@funcx_api.route("/register_endpoint", methods=['POST'])
@authenticated
def reg_endpoint(user: User):
    """Register the endpoint. Add this site to the database and associate it with this user.

    Parameters
    ----------
    user : User
        The primary identity of the user

    Returns
    -------
    json
        A dict containing the endpoint details
    """
    endpoint_name = None
    description = None
    endpoint_uuid = None
    try:
        endpoint_name = request.json["endpoint_name"]
        description = request.json["description"]
    except Exception as e:
        app.logger.error(e)

    if 'endpoint_uuid' in request.json:
        endpoint_uuid = request.json["endpoint_uuid"]

    app.logger.debug(endpoint_name)
    try:
        endpoint_uuid = register_endpoint(
            user, endpoint_name, description, endpoint_uuid)
    except UserNotFound as e:
        return jsonify({'status': 'Failed',
                        'reason': str(e)})

    return jsonify({'endpoint_uuid': endpoint_uuid})


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

    abort(400, "unknown service type or other error.")


@funcx_api.route("/addr", methods=['GET'])
def get_request_addr():
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return jsonify({'ip': request.environ['REMOTE_ADDR']}), 200
    else:
        return jsonify({'ip': request.environ['HTTP_X_FORWARDED_FOR']}), 200


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
            return jsonify({'status': 'Failed',
                            'reason': "Missing Key {}".format(str(e))})
        except Exception as e:
            return jsonify({'status': 'Failed',
                            'reason': 'Request Malformed. Missing critical information: {}'.format(str(e))})
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
            return jsonify({'status': 'Failed',
                            'reason': f'Unauthorized access to endpoint: {endpoint_id}'})
    except Exception as e:
        return jsonify({'status': 'Failed',
                        'reason': f'Endpoint authorization failed. {e}'})

    # TODO add rc to g.
    rc = get_redis_client()

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
        status = {'status': 'Failed',
                  'reason': f'Unable to retrieve endpoint stats: {endpoint_id}. {e}'}

    return jsonify(status)


@funcx_api.route("/register_endpoint_2", methods=['POST'])
@authenticated_w_uuid
def register_endpoint_2(user: User, user_uuid: str):
    """Register an endpoint. Add this endpoint to the database and associate it with this user.

    Returns
    -------
    json
        A dict containing the endpoint details
    """
    app.logger.debug("register_endpoint_2 triggered")
    app.logger.debug(request.json)

    v_info = get_forwarder_version()
    min_ep_version = v_info['min_ep_version']
    if 'version' not in request.json:
        abort(400, "Endpoint funcx version must be passed in the 'version' field.")

    if request.json['version'] < min_ep_version:
        abort(400, f"Endpoint is out of date. Minimum supported endpoint version is {min_ep_version}")

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
        response = {'status': 'error',
                    'reason': f'Missing keys in json request - {e}'}
        return jsonify(response)

    except UserNotFound as e:
        app.logger.exception("User not found")
        response = {'status': 'error',
                    'reason': f'UserNotFound - {e}'}
        return jsonify(response)

    except Exception as e:
        app.logger.exception("Caught error while registering endpoint")
        response = {'status': 'error',
                    'reason': f'Caught error while registering endpoint - {e}'}
        return jsonify(response)

    try:
        forwarder_ip = app.config['FORWARDER_IP']
        response = register_with_hub(
                f"http://{forwarder_ip}:8080", endpoint_uuid, endpoint_ip_addr)
        app.logger.debug(f"Successfully registered {endpoint_uuid} with forwarder")

    except Exception as e:
        app.logger.exception("Caught error during forwarder initialization")
        response = {'status': 'error',
                    'reason': f'Failed during broker start - {e}'}
        return jsonify(response)

    if 'meta' in request.json and endpoint_uuid:
        ingest_endpoint(user.username, user_uuid, endpoint_uuid, request.json['meta'])
        app.logger.debug(f"Ingested endpoint {endpoint_uuid}")

    try:
        return jsonify(response)
    except NameError:
        return "oof"


@funcx_api.route("/register_function", methods=['POST'])
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
                abort(400, f'Container with id {container_uuid} not found')

        group_uuid = request.json.get("group", None)
        group = None
        if group_uuid:
            group = AuthGroup.find_by_uuid(group_uuid)
            if not group:
                abort(400, f"AuthGroup with ID {group_uuid} not found")

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
        abort(400, "Malformed request " + str(key_error))

    except Exception as e:
        message = "Function registration failed for user:{} function_name:{} due to {}".\
            format(user.username, function_rec.function_name, e)
        app.logger.error(message)
        abort(500, message)

    try:
        ingest_function(function_rec, function_source, user_uuid)
    except Exception as e:
        message = "Function ingest to search failed for user:{} function_name:{} due to {}".\
            format(user.username, function_rec.function_name, e)
        app.logger.error(message)
        abort(500, message)

    return response


@funcx_api.route("/upd_function", methods=['POST'])
@authenticated
def upd_function(user: User):
    """Update the function.

        Parameters
        ----------
        user : User
            The primary identity of the user

        Returns
        -------
        json
            Dict containing the result as an integer
        """
    try:
        function_uuid = request.json["func"]
        function_name = request.json["name"]
        function_desc = request.json["desc"]
        function_entry_point = request.json["entry_point"]
        function_code = request.json["code"]
        result = update_function(user.username, function_uuid, function_name,
                                 function_desc, function_entry_point, function_code)

        # app.logger.debug("[LOGGER] result: " + str(result))
        return jsonify({'result': result})
    except Exception as e:
        # app.logger.debug("[LOGGER] funcx.py try statement failed.")
        app.logger.error(e)
        return jsonify({'result': 500})


@funcx_api.route("/delete_function", methods=['POST'])
@authenticated
def del_function(user: User):
    """Delete the function.

        Parameters
        ----------
        user : User
            The primary identity of the user

        Returns
        -------
        json
            Dict containing the result as an integer
        """
    try:
        function_uuid = request.json["func"]
        result = delete_function(user, function_uuid)
        return jsonify({'result': result})
    except Exception as e:
        app.logger.error(e)


@funcx_api.route("/delete_endpoint", methods=['POST'])
@authenticated
def del_endpoint(user: User):
    """Delete the endpoint.

        Parameters
        ----------
        user : User
            The primary identity of the user

        Returns
        -------
        json
            Dict containing the result as an integer
        """
    try:
        endpoint_uuid = request.json["endpoint"]
        result = Endpoint.delete_endpoint(user, endpoint_uuid)
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
            response = {'status': 'Failed',
                        'code': r.status_code,
                        'reason': 'Forwarder did not respond with liveness stats'}
        else:
            response = r.json()
            app.logger.debug(f'Response from forwarder : {response}')
            return response

    except Exception as e:
        response = {'status': 'Failed',
                    'code': 520,
                    'reason': f'Contacting forwarder failed with {e}'}

    return jsonify(response)


@funcx_api.route("/get_map", methods=['GET'])
def get_map():
    """Delete the endpoint.

    Parameters
    ----------
    user_name : str
    The primary identity of the user

    Returns
    -------
    json
    Dict containing the result as an integer
    """
    app.logger.debug("Received map request")
    # return jsonify("hello")
    return send_from_directory('routes', 'mapper.html')
