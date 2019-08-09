import uuid
import json
import time
import os
import shlex
import subprocess
import requests
from requests.models import Response
# import funcx

from version import VERSION
from errors import *

from models.utils import register_endpoint, register_function, get_container, resolve_user
from models.utils import register_container, get_redis_client
from models.utils import resolve_function

from authentication.auth import authorize_endpoint, authenticated
from flask import current_app as app, Blueprint, jsonify, request, abort
from flask import Response
from flask import g
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

    # Parse out the function info
    try:
        post_req = request.json
        endpoint = post_req['endpoint']
        function_uuid = post_req['func']
        input_data = post_req['payload']
    except KeyError as e:
        return jsonify({'status': 'Failed',
                        'reason': "Missing Key {}".format(str(e))})
    except Exception as e:
        return jsonify({'status': 'Failed',
                        'reason': 'Request Malformed. Missing critical information: {}'.format(str(e))})

    try:
        fn_code, fn_entry, container_uuid = resolve_function(user_id, function_uuid)
    except:
        return jsonify({'status': 'Failed',
                        'reason': 'Function UUID:{} could not be resolved'.format(function_uuid)})

    task_id = str(uuid.uuid4())
    # TODO: Check if the user can use the endpoint
    if 'redis_task_queue' not in g:
        g.redis_task_queue = RedisQueue("task",
                                        hostname=app.config['REDIS_HOST'],
                                        port=app.config['REDIS_PORT'])
        g.redis_task_queue.connect()

    app.logger.debug("Got function body :{}".format(fn_code))
    app.logger.debug("Got function entry :{}".format(fn_entry))
    app.logger.debug("Got function container_uuid :{}".format(container_uuid))

    # At this point the packed function body and the args are concatable strings
    payload = fn_code + input_data
    app.logger.debug("Payload : {}".format(payload))

    g.redis_task_queue.put(endpoint, task_id, payload)
    app.logger.debug(f"Task:{task_id} forwarded to Endpoint:{endpoint}")
    app.logger.debug("Redis Queue : {}".format(g.redis_task_queue))
    return jsonify({'status': 'Success',
                    'task_uuid': task_id})


@funcx_api.route('/execute', methods=['POST'])
@authenticated
def execute(user_name):
    """Puts a job in Redis and returns an id

    Parameters
    ----------
    user_name : str
        The primary identity of the user

    Returns
    -------
    json
        The task document
    """

    if not user_name:
        abort(400, description="Could not find user. You must be "
                               "logged in to perform this function.")

    app.logger.debug(f"Received task from user: {user_name}")
    try:
        post_req = request.json
        endpoint = post_req['endpoint']
        function_uuid = post_req['func']
        input_data = post_req['data']

        endpoint_authorized = False
        # Check if the user has already used this endpoint
        if caching and endpoint in endpoint_cache:
            if user_name in endpoint_cache[endpoint]:
                endpoint_authorized = True
        if not endpoint_authorized:
            # Check if the user's token is allowed to access the endpoint
            token = request.headers.get('Authorization')
            token = str.replace(str(token), 'Bearer ', '')

            endpoint_authorized = authorize_endpoint(user_name, endpoint, token)
            # Throw an unauthorized error if they are not allowed
            if not endpoint_authorized:
                return jsonify({"Error": "Unauthorized access of endpoint."}), 400

            # Otherwise, cache it for next time
            if caching:
                if endpoint not in endpoint_cache:
                    endpoint_cache[endpoint] = {}
                endpoint_cache[endpoint][user_name] = True

        task_status = 'ACTIVE'
        task_id = str(uuid.uuid4())

        if 'action_id' in post_req:
            task_id = post_req['action_id']

        app.logger.info("Task assigned UUID: {}".format(task_id))

        # Get the redis connection
        rc = get_redis_client()

        user_id = resolve_user(user_name)

        # Add the job to redis
        task_payload = {'task_id': task_id,
                        'endpoint_id': endpoint,
                        'function_id': function_uuid,
                        'input_data': input_data,
                        'user_name': user_name,
                        'user_id': user_id,
                        'created_at': time.time(),
                        'status': task_status}

        rc.set(f"task:{task_id}", json.dumps(task_payload))

        # Add the task to the redis queue
        rc.rpush("task_list", task_id)

    except Exception as e:
        app.logger.error(e)

    return jsonify({'task_id': task_id})


@funcx_api.route("/debug_post", methods=['POST'])
def debug_post():
    print("HELLO")
    print(request.json)
    r = Response()
    r._content = request.json
    return r


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
            task = json.loads(rc.get(f"results:{task_id}"))
        except:
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
        endpoint_uuid = register_endpoint(user_name, endpoint_name, description, endpoint_uuid)
    except UserNotFound as e:
        return jsonify({'status': 'Failed',
                        'reason': str(e)})

    return jsonify({'endpoint_uuid': endpoint_uuid})

def register_with_hub(address, endpoint_id):
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

    # TODO: We should handle keyError here
    try:
        app.logger.debug(request.json['endpoint_name'])
        endpoint_uuid = register_endpoint(user_name,
                                          request.json['endpoint_name'],
                                          request.json['description'],
                                          request.json['endpoint_uuid'])
    except KeyError as e:
        app.logger.debug("Missing Keys in json request : {}".format(e))
        response = {'status' : 'error',
                    'reason' : 'Missing Keys in json request {e}'.format(e)}
    except Exception as e:
        app.logger.debug("Caught random error : {}".format(e))
        response = {'status' : 'error',
                    'reason' : 'Caught error while registering endpoint {e}'.format(e)}

    try:
        response = register_with_hub("http://34.207.74.221:8080", endpoint_uuid)
    except Exception as e:
        app.logger.debug("Caught error during forwarder initialization")
        response = {'status' : 'error',
                    'reason' : 'Failed during broker start {e}'.format(e)}


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
        container_uuid = None
        if 'container' in request.json:
            container_uuid = request.json["container"]
    except Exception as e:
        app.logger.error(e)

    app.logger.debug(f"Registering function {function_name}")

    try:
        function_uuid = register_function(user_name, function_name, description, function_code, entry_point, container_uuid)
    except Exception as e:
        message = "Function registration failed for user:{} function_name:{}".format(user_name,
                                                                                     function_name)
        app.logger.error(message)
        return jsonify({'status': 'Failed',
                        'reason': message})

    return jsonify({'function_uuid': function_uuid})
