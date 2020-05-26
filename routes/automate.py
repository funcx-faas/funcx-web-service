import uuid
import json
import time
import datetime

from models.utils import resolve_user, get_redis_client
from authentication.auth import authorize_endpoint, authenticated, authorize_function
from models.utils import resolve_function, log_invocation
from flask import current_app as app, Blueprint, jsonify, request, abort, g
from routes.funcx import auth_and_launch

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
        post_req = request.json
        tasks = post_req.get('tasks', None)
        if not tasks:
            # Check if the old client was used and create a new task
            function_uuid = post_req.get('function', None)
            endpoint = post_req.get('endpoint', None)
            input_data = post_req.get('payload', None)
            tasks = [function_uuid, endpoint, input_data]

        # Sets serialize to True by default
        serialize = post_req.get('serialize', True)
    except KeyError as e:
        return jsonify({'status': 'Failed',
                        'reason': "Missing Key {}".format(str(e))})
    except Exception as e:
        return jsonify({'status': 'Failed',
                        'reason': 'Request Malformed. Missing critical information: {}'.format(str(e))})

    results = {'status': 'Success',
               'task_uuids': []}
    for task in tasks:
        res = auth_and_launch(user_id,
                              task[0],
                              [task[1]],
                              task[2],
                              app,
                              token,
                              serialize=serialize)
        if res.get('status', 'Failed') != 'Success':
            return res
        else:
            results['task_uuids'].extend(res['task_uuids'])

    # if the batch size is just one, we can return it as the action id
    if len(results['task_uuids']) == 1:
        action_id = results['task_uuids'][0]
    else:
        # Otherwise we need to create an action id for the batch
        action_id = str(uuid.uuid4())
        # Now store the list of ids in redis with this batch id
        if 'redis_client' not in g:
            g.redis_client = get_redis_client()
        g.redis_client.hset(f'batch_{action_id}', 'batch', json.dumps(results['task_uuids']))

    automate_response = {
        "status": 'ACTIVE',
        "action_id": action_id,
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

    automate_response = {
        "details": None,
        "status": "ACTIVE",
        "action_id": task_id,
        "release_after": 'P30D'
    }

    # Get a redis client
    if 'redis_client' not in g:
        g.redis_client = get_redis_client()

    task_results = None
    # check if it is a batch:
    try:
        task_ids = g.redis_client.hget(f"batch_{task_id}")
        if task_ids:
            # Check the status on all the tasks.
            batch_done = check_batch_status(task_ids)
            if batch_done:
                # Get all of their results
                task_results = []
                for tid in task_ids:
                    task = get_task(tid)
                    task['task_id'] = tid
                    task_results.append(task)

                # If it is done, return it all
                automate_response.details = task_results
                # They all have a success status
                automate_response.status = task['status']
        else:
            # it is not a batch, get the single task result
            task = get_task(task_id)
            task['task_id'] = task_id

            automate_response.details = task
            automate_response.status = task['status']
    except Exception as e:
        app.logger.error(e)
        return jsonify({'status': 'Failed',
                        'reason': 'InternalError: {}'.format(e)})

    return json.dumps(automate_response)


def get_task(task_id):
    """
    Get the task from Redis and delete it if it is finished.

    Parameters
    ----------
    task_id : str
        The task id to check

    Returns
    -------
    Task : dict
    """
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
    return task


def check_batch_status(task_ids):
    """
    Check the status of an entire batch of tasks. Return if ALL of them are complete

    Parameters
    ----------
    task_ids : [str]
        The task ids to check

    Returns
    -------
    If all tasks are complete : bool
    """

    try:
        for task_id in task_ids:
            result_obj = g.redis_client.hget(f"task_{task_id}", 'result')
            app.logger.debug(f"Result_obj : {result_obj}")
            if not result_obj:
                return False
    except Exception as e:
        return False
    return True
