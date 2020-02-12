import uuid
import json
import time
import requests
from requests.models import Response

from version import VERSION
from errors import *

from models.utils import register_endpoint, register_function, get_container, resolve_user
from models.utils import register_container, get_redis_client
from models.utils import resolve_function, log_invocation
from models.utils import update_function, delete_function, delete_endpoint

from authentication.auth import authorize_endpoint, authenticated, authorize_function
from flask import current_app as app, Blueprint, jsonify, request, abort, send_from_directory, g

from .redis_q import RedisQueue

# Flask
funcx_api = Blueprint("routes", __name__)

# A cache for authorized endpoint usage by users
endpoint_cache = {}

caching = True


@funcx_api.route('/submit', methods=['POST'])
@authenticated
def submit(user_name):
    """Puts the task request into Redis and returns a task UUID
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
    app.logger.debug(f"Submit invoked by user:{user_name}")

    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")
    try:
        user_id = resolve_user(user_name)
    except Exception:
        app.logger.error("Failed to resolve user_name to user_id")
        return jsonify({'status': 'Failed',
                        'reason': 'Failed to resolve user_name:{}'.format(user_name)})

    # Extract the token for endpoint verification
    token_str = request.headers.get('Authorization')
    token = str.replace(str(token_str), 'Bearer ', '')

    # Parse out the function info
    try:
        post_req = request.json
        endpoint = post_req['endpoint']
        function_uuid = post_req['func']
        input_data = post_req['payload']
        serializer = None
        if 'serializer' in post_req:
            serializer = post_req['serializer']
    except KeyError as e:
        return jsonify({'status': 'Failed',
                        'reason': "Missing Key {}".format(str(e))})
    except Exception as e:
        return jsonify({'status': 'Failed',
                        'reason': 'Request Malformed. Missing critical information: {}'.format(str(e))})

    # Check if the user is allowed to access the function
    if not authorize_function(user_id, function_uuid, token):
        return jsonify({'status': 'Failed',
                        'reason': f'Unauthorized access to function: {function_uuid}'})

    try:
        fn_code, fn_entry, container_uuid = resolve_function(
            user_id, function_uuid)
    except Exception as e:
        return jsonify({'status': 'Failed',
                        'reason': f'Function UUID:{function_uuid} could not be resolved. {e}'})

    if isinstance(endpoint, str):
        endpoint = [endpoint]

    # Make sure the user is allowed to use the endpoint
    for ep in endpoint:
        if not authorize_endpoint(user_id, ep, token):
            return jsonify({'status': 'Failed',
                            'reason': f'Unauthorized access to endpoint: {ep}'})

    task_id = str(uuid.uuid4())

    app.logger.debug("Got function container_uuid :{}".format(container_uuid))

    # At this point the packed function body and the args are concatable strings
    payload = fn_code + input_data
    app.logger.debug("Payload : {}".format(payload))

    if not container_uuid:
        container_uuid = 'RAW'

    if not serializer:
        serializer = "ANY"

    task_header = f"{task_id};{container_uuid};{serializer}"

    # TODO: Store redis connections in g
    rc = get_redis_client()

    for ep in endpoint:
        redis_task_queue = RedisQueue(f"task_{ep}",
                                      hostname=app.config['REDIS_HOST'],
                                      port=app.config['REDIS_PORT'])
        redis_task_queue.connect()

        redis_task_queue.put(task_header, 'task', payload)
        app.logger.debug(f"Task:{task_id} forwarded to Endpoint:{ep}")
        app.logger.debug("Redis Queue : {}".format(redis_task_queue))

        # TODO: creating these connections each will be slow.
        # increment the counter
        rc.incr('funcx_invocation_counter')
        # add an invocation to the database
        log_invocation(user_id, task_id, function_uuid, ep)


    return jsonify({'status': 'Success',
                    'task_uuid': task_id})


@funcx_api.route("/<task_id>/status", methods=['GET'])
@authenticated
def status(user_name, task_id):
    """Check the status of a task.

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

    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")

    try:
        # Get a redis client
        rc = get_redis_client()

        details = {}

        # Get the task from redis
        try:
            result_obj = rc.hget(f"task_{task_id}", 'result')
            app.logger.debug(f"Result_obj : {result_obj}")
            if result_obj:
                task = json.loads(result_obj)
            else:
                task = {'status': 'PENDING'}
        except Exception as e:
            app.logger.error(f"Failed to fetch results for {task_id} due to {e}")
            task = {'status': 'FAILED', 'reason': 'Unknown task id'}
        else:
            if result_obj:
                # Task complete, attempt flush
                try:
                    rc.delete(f"task_{task_id}")
                except Exception as e:
                    app.logger.warning(f"Failed to delete Task:{task_id} due to {e}. Ignoring...")
                    pass

        res = {'task_id': task_id}

        task['task_id'] = task_id

        app.logger.debug("Status Response: {}".format(str(task)))
        return jsonify(task)

    except Exception as e:
        app.logger.error(e)
        return jsonify({'status': 'Failed',
                        'reason': 'InternalError: {}'.format(e)})


@funcx_api.route("/<task_id>/result", methods=['GET'])
@authenticated
def result(user_name, task_id):
    """Check the status of a task.

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

    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")

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


@funcx_api.route("/tasks/<task_id>", methods=['GET'])
@authenticated
def get_task(user_name, task_id):
    """Get a task.

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

    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")

    try:
        # Get a redis client
        rc = get_redis_client()

        # Get the task from redis
        try:
            result_obj = rc.hget(f"task_{task_id}", 'result')
            app.logger.debug(f"Result_obj : {result_obj}")
            if result_obj:
                task = json.loads(result_obj)
                if 'status' not in task:
                    task['status'] = 'COMPLETED'
            else:
                task = {'status': 'PENDING'}
        except Exception as e:
            app.logger.error(f"Failed to fetch results for {task_id} due to {e}")
            task = {'status': 'FAILED', 'reason': 'Unknown task id'}
        else:
            if result_obj:
                # Task complete, attempt flush
                try:
                    rc.delete(f"task_{task_id}")
                except Exception as e:
                    app.logger.warning(f"Failed to delete Task:{task_id} due to {e}. Ignoring...")
                    pass

        task['task_id'] = task_id

        app.logger.debug("Status Response: {}".format(str(task['status'])))
        return jsonify(task)

    except Exception as e:
        app.logger.error(e)
        return jsonify({'status': 'FAILED',
                        'reason': 'InternalError: {}'.format(e)})


@funcx_api.route("/tasks/<task_id>/status", methods=['GET'])
@authenticated
def get_task_status(user_name, task_id):
    """Check the status of a task.

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

    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")

    try:
        # Get a redis client
        rc = get_redis_client()

        # Get the task from redis
        try:
            result_obj = rc.hget(f"task_{task_id}", 'result')
            app.logger.debug(f"Result_obj : {result_obj}")
            if result_obj:
                task = json.loads(result_obj)
                if 'status' not in task:
                    task['status'] = 'COMPLETED'
            else:
                task = {'status': 'PENDING'}
        except Exception as e:
            app.logger.error(f"Failed to fetch results for {task_id} due to {e}")
            task = {'status': 'FAILED', 'reason': 'Unknown task id'}

        app.logger.debug("Status Response: {}".format(str(task['status'])))
        return jsonify({'status': task['status']})

    except Exception as e:
        app.logger.error(e)
        return jsonify({'status': 'FAILED',
                        'reason': 'InternalError: {}'.format(e)})


@funcx_api.route("/containers/<container_id>/<container_type>", methods=['GET'])
@authenticated
def get_cont(user_name, container_id, container_type):
    """Get the details of a container.

    Parameters
    ----------
    user_name : str
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

    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")
    app.logger.debug(f"Getting container details: {container_id}")
    container = get_container(container_id, container_type)
    app.logger.debug(f"Got container: {container}")
    return jsonify({'container': container})


@funcx_api.route("/containers", methods=['POST'])
@authenticated
def reg_container(user_name):
    """Register a new container.

    Parameters
    ----------
    user_name : str
        The primary identity of the user

    Returns
    -------
    dict
        A dictionary of container details including its uuid
    """

    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")

    app.logger.debug(f"Creating container.")
    post_req = request.json

    container_id = register_container(user_name, post_req['name'], post_req['location'],
                                      post_req['description'], post_req['type'])
    app.logger.debug(f"Created container: {container_id}")
    return jsonify({'container_id': container_id})


@funcx_api.route("/register_endpoint", methods=['POST'])
@authenticated
def reg_endpoint(user_name):
    """Register the endpoint. Add this site to the database and associate it with this user.

    Parameters
    ----------
    user_name : str
        The primary identity of the user

    Returns
    -------
    json
        A dict containing the endpoint details
    """
    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")
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
            user_name, endpoint_name, description, endpoint_uuid)
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
    r = requests.post(address + '/register',
                      json={'endpoint_id': endpoint_id,
                            'redis_address': 'funcx-redis.wtgh6h.0001.use1.cache.amazonaws.com',
                            'endpoint_addr': endpoint_address,
                            }
                      )
    if r.status_code != 200:
        print(dir(r))
        print(r)
        raise RegistrationError(r.reason)

    return r.json()


@funcx_api.route("/version", methods=['GET'])
def get_version():
    return jsonify(VERSION)


@funcx_api.route("/addr", methods=['GET'])
def get_request_addr():
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        return jsonify({'ip': request.environ['REMOTE_ADDR']}), 200
    else:
        return jsonify({'ip': request.environ['HTTP_X_FORWARDED_FOR']}), 200


@funcx_api.route("/register_endpoint_2", methods=['POST'])
@authenticated
def register_endpoint_2(user_name):
    """Register an endpoint. Add this endpoint to the database and associate it with this user.

    Returns
    -------
    json
        A dict containing the endpoint details
    """
    app.logger.debug("register_endpoint_2 triggered")

    if not user_name:
        abort(400, description="Error: You must be logged in to perform this function.")

    # Cooley ALCF is the default used here.
    endpoint_ip_addr = '140.221.68.108'
    if request.environ.get('HTTP_X_FORWARDED_FOR') is None:
        endpoint_ip_addr = request.environ['REMOTE_ADDR']
    else:
        endpoint_ip_addr = request.environ['HTTP_X_FORWARDED_FOR']
    app.logger.debug(f"Registering endpoint IP address as: {endpoint_ip_addr}")

    try:
        app.logger.debug(request.json['endpoint_name'])
        endpoint_uuid = register_endpoint(user_name,
                                          request.json['endpoint_name'],
                                          request.json['description'],
                                          request.json['endpoint_uuid'])

    except KeyError as e:
        app.logger.debug("Missing Keys in json request : {}".format(e))
        response = {'status': 'error',
                    'reason': f'Missing Keys in json request {e}'}

    except UserNotFound as e:
        app.logger.debug(f"UserNotFound {e}")
        response = {'status': 'error',
                    'reason': f'UserNotFound {e}'}

    except Exception as e:
        app.logger.debug("Caught random error : {}".format(e))
        response = {'status': 'error',
                    'reason': f'Caught error while registering endpoint {e}'}

    try:
        forwarder_ip = app.config['FORWARDER_IP']
        response = register_with_hub(
            f"http://{forwarder_ip}:8080", endpoint_uuid, endpoint_ip_addr)
    except Exception as e:
        app.logger.debug("Caught error during forwarder initialization")
        response = {'status': 'error',
                    'reason': f'Failed during broker start {e}'}

    return jsonify(response)


@funcx_api.route("/register_function", methods=['POST'])
@authenticated
def reg_function(user_name):
    """Register the function.

    Parameters
    ----------
    user_name : str
        The primary identity of the user

    POST Payload
    ------------
    { "function_name" : <FN_NAME>,
      "entry_point" : <ENTRY_POINT>,
      "function_code" : <ENCODED_FUNTION_BODY>,
      "container_uuid" : <CONTAINER_UUID>,
      "description" : <DESCRIPTION>
    }

    Returns
    -------
    json
        Dict containing the function details
    """
    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")
    try:

        function_name = request.json["function_name"]
        entry_point = request.json["entry_point"]
        description = request.json["description"]
        function_code = request.json["function_code"]
        container_uuid = request.json.get("container_uuid", None)

    except Exception as e:
        app.logger.error(e)

    app.logger.debug(f"Registering function {function_name} with container {container_uuid}")

    try:
        function_uuid = register_function(
            user_name, function_name, description, function_code, entry_point, container_uuid)
    except Exception as e:
        message = "Function registration failed for user:{} function_name:{} due to {}".format(
            user_name,
            function_name,
            e)
        app.logger.error(message)
        return jsonify({'status': 'Failed',
                        'reason': message})

    return jsonify({'function_uuid': function_uuid})


@funcx_api.route("/upd_function", methods=['POST'])
@authenticated
def upd_function(user_name):
    """Update the function.

        Parameters
        ----------
        user_name : str
            The primary identity of the user

        Returns
        -------
        json
            Dict containing the result as an integer
        """
    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")
    try:
        function_uuid = request.json["func"]
        function_name = request.json["name"]
        function_desc = request.json["desc"]
        function_entry_point = request.json["entry_point"]
        function_code = request.json["code"]
        result = update_function(user_name, function_uuid, function_name,
                                 function_desc, function_entry_point, function_code)
        # app.logger.debug("[LOGGER] result: " + str(result))
        return jsonify({'result': result})
    except Exception as e:
        # app.logger.debug("[LOGGER] funcx.py try statement failed.")
        app.logger.error(e)
        return jsonify({'result': 500})


@funcx_api.route("/delete_function", methods=['POST'])
@authenticated
def del_function(user_name):
    """Delete the function.

        Parameters
        ----------
        user_name : str
            The primary identity of the user

        Returns
        -------
        json
            Dict containing the result as an integer
        """
    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")
    try:
        function_uuid = request.json["func"]
        result = delete_function(user_name, function_uuid)
        return jsonify({'result': result})
    except Exception as e:
        app.logger.error(e)


@funcx_api.route("/delete_endpoint", methods=['POST'])
@authenticated
def del_endpoint(user_name):
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
    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")
    try:
        endpoint_uuid = request.json["endpoint"]
        result = delete_endpoint(user_name, endpoint_uuid)
        return jsonify({'result': result})
    except Exception as e:
        app.logger.error(e)


@funcx_api.route("/ep_live", methods=['GET'])
def get_stats_from_forwarder(forwarder_address="http://10.0.0.112:8080"):
    """ Get stats from the forwarder
    """
    app.logger.debug(f"Getting stats from forwarder")
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
    app.logger.debug(f"Received map request")
    # return jsonify("hello")
    return send_from_directory('routes', 'mapper.html')
