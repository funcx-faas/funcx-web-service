import psycopg2.extras
import datetime
import pickle
import uuid
import json
import time

from .utils import (_get_user, _log_request,
                    _register_site, _register_function, _authorize_endpoint,
                    _resolve_function, _introspect_token, _get_container)
from flask import current_app as app, Blueprint, jsonify, request, abort
from config import _get_db_connection, _get_redis_client

# Flask
automate = Blueprint("automate", __name__)

token_cache = {}
endpoint_cache = {}
caching = True


@automate.route('/run', methods=['POST'])
def run():
    """Execute the specified function

    Returns
    -------
    json
        The task document
    """

    token = None
    if 'Authorization' in request.headers:
        token = request.headers.get('Authorization')
        token = token.split(" ")[1]
    else:
        abort(400, description=f"You must be logged in to perform this function.")

    if caching and token in token_cache:
        user_id, user_name, short_name = token_cache[token]
    else:
        # Perform an Auth call to get the user name
        user_id, user_name, short_name = _get_user(request.headers)
        token_cache['token'] = (user_id, user_name, short_name)

    if not user_name:
        abort(400, description=f"Could not find user. You must be logged in to perform this function.")

    try:
        print("Starting the request")
        post_req = request.json['body']
        endpoint = post_req['endpoint']
        function_uuid = post_req['func']
        input_data = post_req['data']

        endpoint_authorized = False
        # Check if the user has already used this endpoint
        if caching and endpoint in endpoint_cache:
            if user_name in endpoint_cache[endpoint]:
                endpoint_authorized = True
        if not endpoint_authorized:
            # Check if the user is allowed to access the endpoint
            endpoint_authorized = _authorize_endpoint(user_id, endpoint, token)
            # Throw an unauthorized error if they are not allowed
            if not endpoint_authorized:
                abort(400, description=f"Unauthorized access of endpoint.")

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
        print(task_id)
        # Get the redis connection
        rc = _get_redis_client()

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

    automate_response = {
        "status": task_status,
        "action_id": task_id,
        "details": None,
        "release_after": 'P30D',
        "start_time": str(datetime.datetime.utcnow())
    }
    print(automate_response)
    return jsonify(automate_response)


@automate.route("/<task_id>/status", methods=['GET'])
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

    token = None
    if 'Authorization' in request.headers:
        token = request.headers.get('Authorization')
        token = token.split(" ")[1]
    else:
        abort(400, description=f"You must be logged in to perform this function.")

    if caching and token in token_cache:
        user_name, user_id, short_name = token_cache[token]
    else:
        # Perform an Auth call to get the user name
        user_name, user_id, short_name = _get_user(request.headers)
        token_cache[token] = (user_name, user_id, short_name)

    if not user_name:
        abort(400, description="Could not find user. You must be logged in to perform this function.")

    try:
        # Get a redis client
        rc = _get_redis_client()

        details = {}

        # Get the task from redis
        try:
            task = json.loads(rc.get(f"task:{task_id}"))
        except:
            task = {'status': 'FAILED', 'reason': 'Unknown task id'}

        if 'result' in task:
            details['result'] = task['result']
        if 'reason' in task:
            details['reason'] = task['reason']

        automate_response = {
            "details": details,
            "status": task['status'],
            "action_id": task_id,
            "release_after": 'P30D'
        }
        return json.dumps(automate_response)

    except Exception as e:
        app.logger.error(e)
        return json.dumps({'InternalError': e})
