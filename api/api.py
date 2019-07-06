import psycopg2.extras
import pickle
import uuid
import json
import time

from .utils import (_get_user, _create_task, _update_task, _log_request, 
                    _register_site, _register_function, _resolve_endpoint,
                    _resolve_function, _introspect_token, _get_container)
from flask import current_app as app, Blueprint, jsonify, request, abort
from config import _get_db_connection, _get_redis_client
from utils.majordomo_client import ZMQClient

# Flask
api = Blueprint("api", __name__)

zmq_client = ZMQClient("tcp://localhost:50001")

token_cache = {}
caching = True


@api.route('/execute', methods=['POST'])
def execute():
    """Puts a job in Redis and returns an id

    Returns
    -------
    json
        The task document
    """
#    token = None
#    if 'Authorization' in request.headers:
#        token = request.headers.get('Authorization')
#        token = token.split(" ")[1]
#    else:
#        abort(400, description="Error: You must be logged in to perform this function.")
#
#    if caching and token in token_cache:
#        user_id, user_name, short_name = token_cache[token]
#    else:
#        # Perform an Auth call to get the user name
#        user_id, user_name, short_name = _get_user(request.headers)
#        token_cache.update({token: (user_id, user_name, short_name)})

    user_id = 1
    user_name = 'ryan@globusid.org'
    short_name = 'ryan_globusid'

    if not user_name:
        abort(400, description="Error: You must be logged in to perform this function.")

    try:
        post_req = request.json
        endpoint = post_req['endpoint']
        function_uuid = post_req['func']
        input_data = post_req['data']

        task_id = str(uuid.uuid4())

        if 'action_id' in post_req:
            task_id = post_req['action_id']

        app.logger.info("Task assigned UUID: {}".format(task_id))

        # Get the redis connection
        rc = _get_redis_client()
        
        # Add the job to redis
        task_payload = {'endpoint_id': endpoint,
                        'function_id': function_uuid,
                        'input_data': input_data,
                        'user_name': user_name,
                        'user_id': user_id,
                        'created_at': time.time(),
                        'status': 'PENDING'}
        
        rc.set(f"task:{task_id}", json.dumps(task_payload))

        # Add the task to the redis queue
        rc.rpush("task_list", task_id)

    except Exception as e:
        app.logger.error(e)

    return jsonify({'task_id': task_id})


@api.route("/<task_id>/status", methods=['GET'])
def status(task_id):
    """Check the status of a task.

    Parameters
    ----------
    task_id : str
        The task uuid to look up

    Returns
    -------
    json
        The status of the task
    """

#    token = None
#    if 'Authorization' in request.headers:
#        token = request.headers.get('Authorization')
#        token = token.split(" ")[1]
#    else:
#        abort(400, description="Error: You must be logged in to perform this function.")
#
#    if caching and token in token_cache:
#        user_name = token_cache[token]
#    else:
#        # Perform an Auth call to get the user name
#        user_name = _introspect_token(request.headers)
#        token_cache.update({token: user_name})


    user_id = 1
    user_name = 'ryan@globusid.org'
    short_name = 'ryan_globusid'


    if not user_name:
        abort(400, description="Error: You must be logged in to perform this function.")

    try:
        # Get a redis client
        rc = _get_redis_client()

        # Get the task from redis
        task = json.loads(rc.get(f"task:{task_id}"))

        res = {'task_id': task_id}
        details = {}
        if 'status' in task:
            res['status'] = task['status']

        if 'result' in task:
            details['result'] = task['result']
        if 'reason' in task:
            details['reason'] = task['reason']

        if details:
            res.update({'details': details})

        app.logger.debug("Status Response: {}".format(str(res)))
        return json.dumps(res)

    except Exception as e:
        app.logger.error(e)
        return json.dumps({'InternalError': e})


@api.route("/containers/<container_id>/<container_type>", methods=['GET'])
def get_container(container_id, container_type):
    """Get the details of a container.

    Parameters
    ----------
    container_id : str
        The id of the container
    container_type : str
        The type of containers to return: Docker, Singularity, Shifter, etc.

    Returns
    -------
    dict
        A dictionary of container details
    """
    user_id, user_name, short_name = _get_user(request.headers)
    if not user_name:
        abort(400, description="Error: You must be logged in to perform this function.")
    app.logger.debug(f"Getting container details: {container_id}")
    container = _get_container(user_id, container_id, container_type)
    print(container)
    return jsonify({'container': container})


@api.route("/register_endpoint", methods=['POST'])
def register_site():
    """Register the site. Add this site to the database and associate it with this user.

    Returns
    -------
    json
        A dict containing the endpoint details
    """
    user_id, user_name, short_name = _get_user(request.headers)
    if not user_name:
        abort(400, description="Error: You must be logged in to perform this function.")
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
    endpoint_uuid = _register_site(user_id, endpoint_name, description, endpoint_uuid)
    return jsonify({'endpoint_uuid': endpoint_uuid})


@api.route("/register_function", methods=['POST'])
def register_function():
    """Register the function.

    Returns
    -------
    json
        Dict containing the function details
    """
    user_id, user_name, short_name = _get_user(request.headers)
    if not user_name:
        abort(400, description="Error: You must be logged in to perform this function.")
    try:
        function_name = request.json["function_name"]
        entry_point = request.json["entry_point"]
        description = request.json["description"]
        function_code = request.json["function_code"]
    except Exception as e:
        app.logger.error(e)
    app.logger.debug(function_name)
    function_uuid = _register_function(user_id, function_name, description, function_code, entry_point)
    return jsonify({'function_uuid': function_uuid})

