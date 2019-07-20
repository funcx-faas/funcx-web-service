import uuid
import json
import time
import datetime

from models.utils import resolve_user, get_redis_client
from authentication.auth import authorize_endpoint, authenticated
from flask import current_app as app, Blueprint, jsonify, request, abort

# Flask
automate_api = Blueprint("automate", __name__)

token_cache = {}
endpoint_cache = {}
caching = True


@automate_api.route('/run', methods=['POST'])
@authenticated
def run(user_name):
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

    try:
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
            endpoint_authorized = authorize_endpoint(user_name, endpoint, request)
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
        print(task_id)
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

    automate_response = {
        "status": task_status,
        "action_id": task_id,
        "details": None,
        "release_after": 'P30D',
        "start_time": str(datetime.datetime.utcnow())
    }
    print(automate_response)
    return jsonify(automate_response)


@automate_api.route("/<task_id>/status", methods=['GET'])
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
