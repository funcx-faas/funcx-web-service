import uuid
import json
import time
import datetime

from models.utils import resolve_user, get_redis_client
from authentication.auth import authorize_endpoint, authenticated, authorize_function
from models.utils import resolve_function, log_invocation
from flask import current_app as app, Blueprint, jsonify, request, abort, g

from models.serializer import serialize_inputs, deserialize_result

from .redis_q import RedisQueue

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

    app.logger.debug(f"Automate submit invoked by user:{user_name}")

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
        post_req = request.json['body']
        endpoint = post_req['endpoint']
        function_uuid = post_req['func']
        input_data = post_req['payload']
        serialize = post_req.get('serialize', None)
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
    except:
        return jsonify({'status': 'Failed',
                        'reason': 'Function UUID:{} could not be resolved'.format(function_uuid)})

    if isinstance(endpoint, str):
        endpoint = [endpoint]

    for ep in endpoint:
        if not authorize_endpoint(user_id, ep, function_uuid, token):
            return jsonify({'status': 'Failed',
                            'reason': f'Unauthorized access to endpoint: {ep}'})

    task_id = str(uuid.uuid4())

    app.logger.debug("Got function container_uuid :{}".format(container_uuid))

    if serialize:
        res = serialize_inputs(input_data)
        if res:
            input_data = res
        else:
            return jsonify({'status': 'Failed',
                           'reason': 'Unable to serialize input data'})

    # At this point the packed function body and the args are concatable strings
    payload = fn_code + input_data
    app.logger.debug("Payload : {}".format(payload))

    if not container_uuid:
        container_uuid = 'RAW'

    # TODO: This is deprecated.
    serializer = "ANY"

    task_header = f"{task_id};{container_uuid};{serializer}"

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

    automate_response = {
        "status": 'ACTIVE',
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
        if 'redis_client' not in g:
            g.redis_client = get_redis_client()

        task = {}

        # Get the task from redis
        try:
            result_obj = g.redis_client.hget(f"task_{task_id}", 'result')
            app.logger.debug(f"Result_obj : {result_obj}")
            if result_obj:
                task = json.loads(result_obj)
                if 'status' not in task:
                    task['status'] = 'SUCCEEDED'
                if 'result' in task:
                    # deserialize the result for Automate to consume
                    task['result'] = deserialize_result(task['result'])
            else:
                task = {'status': 'ACTIVE'}
        except Exception as e:
            app.logger.error(f"Failed to fetch results for {task_id} due to {e}")
            task = {'status': 'FAILED', 'reason': 'Unknown task id'}
        else:
            if result_obj:
                # Task complete, attempt flush
                try:
                    g.redis_client.delete(f"task_{task_id}")
                except Exception as e:
                    app.logger.warning(f"Failed to delete Task:{task_id} due to {e}. Ignoring...")
                    pass

        task['task_id'] = task_id

        automate_response = {
            "details": task,
            "status": task['status'],
            "action_id": task_id,
            "release_after": 'P30D'
        }
        return json.dumps(automate_response)

    except Exception as e:
        app.logger.error(e)
        return jsonify({'status': 'Failed',
                        'reason': 'InternalError: {}'.format(e)})
