import uuid
import json
import datetime

from models.tasks import Task
from models.utils import resolve_user, get_redis_client
from authentication.auth import authenticated
from flask import current_app as app, Blueprint, jsonify, request, abort, g
from routes.funcx import auth_and_launch

from models.serializer import deserialize_result

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
    tasks = []
    try:
        post_req = request.json['body']
        if 'tasks' in post_req:
            tasks = post_req.get('tasks', [])
        else:
            # Check if the old client was used and create a new task
            function_uuid = post_req.get('func', None)
            endpoint = post_req.get('endpoint', None)
            input_data = post_req.get('payload', None)
            tasks.append({'func': function_uuid, 'endpoint': endpoint, 'payload': input_data})

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
    app.logger.info(f'tasks to submit: {tasks}')
    for task in tasks:
        res = auth_and_launch(user_id,
                              task['func'],
                              [task['endpoint']],
                              task['payload'],
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
        rc = get_redis_client()
        rc.hset(f'batch_{action_id}', 'batch', json.dumps(results['task_uuids']))

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

    rc = get_redis_client()

    task_results = None
    # check if it is a batch:
    try:
        task_ids = rc.hget(f"batch_{task_id}", "batch")
        app.logger.info(f"batch task_ids: {task_ids}")

        if task_ids:
            task_ids = json.loads(task_ids)
            # Check the status on all the tasks.
            batch_done = check_batch_status(task_ids)
            if batch_done:
                # Get all of their results
                task_results = []
                for tid in task_ids:
                    task = get_task_result(tid, delete=False)
                    task['task_id'] = tid
                    task_results.append(task)

                # If it is done, return it all
                automate_response['details'] = task_results
                # They all have a success status
                automate_response['status'] = task['status']
        else:
            # it is not a batch, get the single task result
            task = get_task_result(task_id, delete=False)
            task['task_id'] = task_id

            automate_response['details'] = task
            automate_response['status'] = task['status']
    except Exception as e:
        app.logger.error(e)
        return jsonify({'status': 'Failed',
                        'reason': 'InternalError: {}'.format(e)})

    return json.dumps(automate_response)


@automate_api.route("/<task_id>/release", methods=['POST'])
@authenticated
def release(user_name, task_id):
    """
    Release the task. This does nothing as we already released the task.
    """

    automate_response = {
        "details": None,
        "status": "SUCCEEDED",
        "action_id": task_id,
        "release_after": 'P30D'
    }

    rc = get_redis_client()

    task_results = None
    # check if it is a batch:
    try:
        task_ids = rc.hget(f"batch_{task_id}", "batch")
        app.logger.info(f"batch task_ids: {task_ids}")

        if task_ids:
            task_ids = json.loads(task_ids)
            # Check the status on all the tasks.
            batch_done = check_batch_status(task_ids)
            if batch_done:
                # Get all of their results
                task_results = []
                for tid in task_ids:
                    task = get_task_result(tid)
                    task['task_id'] = tid
                    task_results.append(task)

                # If it is done, return it all
                automate_response['details'] = task_results
                # They all have a success status
                automate_response['status'] = task['status']
        else:
            # it is not a batch, get the single task result
            task = get_task_result(task_id)
            task['task_id'] = task_id

            automate_response['details'] = task
            automate_response['status'] = task['status']
    except Exception as e:
        app.logger.error(e)
        return jsonify({'status': 'Failed',
                        'reason': 'InternalError: {}'.format(e)})

    return json.dumps(automate_response)


def get_task_result(task_id, delete=True):
    """Check the status of a task. Return result if available.

    If the query param deserialize=True is passed, then we deserialize the result object.

    Parameters
    ----------
    task_id : str
        The task uuid to look up
    delete : bool
        Whether or not to remove the task from the database

    Returns
    -------
    json
        The task as a dict
    """
    rc = get_redis_client()

    if not Task.exists(rc, task_id):
        abort(400, "task_id not found")

    task_dict = {}

    task = Task.from_id(rc, task_id)
    task_dict['status'] = convert_automate_status(task.status)
    task_dict['result'] = task.result
    task_dict['exception'] = task.exception
    task_dict['completion_t'] = task.completion_time
    if (task_dict['result'] or task_dict['exception']) and delete:
        task.delete()

    if task_dict['result']:
        task_dict['result'] = deserialize_result(task_dict['result'])

    return task_dict


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

    rc = get_redis_client()

    try:
        for task_id in task_ids:
            app.logger.debug(f"Checking task id for: task_{task_id}")
            result_obj = rc.hget(f"task_{task_id}", 'result')
            app.logger.debug(f"Batch Result_obj : {result_obj}")
            if not result_obj:
                return False
    except Exception as e:
        return False
    return True


def convert_automate_status(task_status):
    """Convert the status response to one that works with Automate.

    The status code needs to be one of:
      - SUCCEEDED
      - FAILED
      - ACTIVE
      - INACTIVE

    Parameters
    ----------
    task_status : str
        The status code reported by funcX tasks

    Returns
    -------
    str : One of the above status codes.
    """
    response = "FAILED"

    if task_status == "success":
        response = "SUCCEEDED"
    elif task_status in ["received", "waiting-for-ep", "waiting-for-nodes",
                         "waiting-for-launch", "running"]:
        response = "ACTIVE"

    return response
