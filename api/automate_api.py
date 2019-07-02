import psycopg2.extras
import pickle
import uuid
import json
import time
import statistics
import base64
from random import randint
from datetime import timezone, timedelta, datetime
from .utils import (_get_user, _create_task, _update_task, _log_request, 
                    _register_site, _register_function, _resolve_endpoint,
                    _resolve_function, _introspect_token, _get_container)
from flask import current_app as app, Blueprint, jsonify, request, abort
from config import _get_db_connection
from utils.majordomo_client import ZMQClient
import threading

# Flask
automate = Blueprint("automate", __name__)

zmq_client = ZMQClient("tcp://localhost:50001")

user_cache = {}
function_cache = {}
endpoint_cache = {}

caching = True


def async_funcx(task_uuid, endpoint_id, obj):
    """Run the function async and update the database.

    Parameters
    ----------
        task_uuid : str
            name of the endpoint
        endpoint_id : string
            str describing the site
        obj : tuple
            object to pass to the zmq client
    """

    _update_task(task_uuid, "RUNNING")
    res = zmq_client.send(endpoint_id, obj)
    _update_task(task_uuid, "SUCCEEDED", result=res)


@automate.route('/run', methods=['POST'])
def run():
    """Execute the specified function

    Returns
    -------
    json
        The task document
    """
    now = datetime.now(tz=timezone.utc)
    #body = req["body"]
    # Generate an action_id for this instance of the action:
    app.logger.debug("Executing function...")

    user_name = _introspect_token(request.headers)

    if caching and user_name in user_cache:
        app.logger.debug("Getting user_id FROM CACHE")
        user_id, short_name = user_cache[user_name]

    else:
        app.logger.debug("User ID not in cache -- fetching from DB")
        user_id, user_name, short_name = _get_user(request.headers)
        if caching:
            user_cache[user_name] = (user_id, short_name)

    try:
        post_req = request.json

        print(post_req)
        post_req = post_req['body']
        endpoint = post_req['endpoint']
        function_uuid = post_req['func']
        is_async = post_req['is_async']
        input_data = post_req['data']
        # Check to see if function in cache. OTHERWISE go get it. 
        # TODO: Cache flushing -- do LRU or something.
        # TODO: Move this to the RESOLVE function (not here).
        if caching and function_uuid in function_cache:
            app.logger.debug("Fetching function from function cache...")
            func_code, func_entry = function_cache[function_uuid]
        else:
            app.logger.debug("Function name not in cache -- fetching from DB...")
            func_code, func_entry = _resolve_function(user_id, function_uuid)
            
            # Now put it INTO the cache! 
            if caching:
                function_cache[function_uuid] = (func_code, func_entry)

        endpoint_id = _resolve_endpoint(user_id, endpoint, status='ONLINE')
        if endpoint_id is None:
            return jsonify({"status": "ERROR", "message": str("Invalid endpoint")})
    except Exception as e:
        app.logger.error(e)

    task_uuid = str(uuid.uuid4())
    app.logger.info("Task assigned UUID: ".format(task_uuid))
    # Create task entry in DB with status "PENDING"
    task_status = "ACTIVE"
    task_res = _create_task(user_id, task_uuid, is_async, task_status)
    default_release_after = timedelta(days=30)
    if 'action_id' in post_req:
        task_uuid = post_req['action_id']
    job = {
        "status":task_status,
        "action_id": task_uuid,
        # Default these to the principals of whoever is running this action:
        #"manage_by": request.auth.identities,
        #"monitor_by": request.auth.identities,
        #"creator_id": request.auth.effective_identity,
        "release_after": 'P30D',
        "start_time":str(datetime.utcnow()) 
    }
    print('hi')
    time.sleep(5)
    try:
        # Spin off thread to communicate with Parsl service.
        # multi_thread_launch("parsl-thread", str(task_uuid), cmd, is_async)

        exec_flag = 1
        # Future proofing for other exec types

        event = {'data': input_data, 'context': {}}

        data = {"function": func_code, "entry_point": func_entry, 'event': event}
        # Set the exec site
        site = "local"
        obj = (exec_flag, task_uuid, data)
        
        if is_async:
            app.logger.debug("Processing async request...")
            task_status = "ACTIVE"
            thd = threading.Thread(target=async_funcx, args=(task_uuid, endpoint_id, obj))
            res = task_uuid
            thd.start()
        else:
            app.logger.debug("Processing sync request...")
            res = zmq_client.send(endpoint_id, obj)
            res = pickle.loads(res)
            task_status = "SUCCEEDED"
            _update_task(task_uuid, task_status)

    # Minor TODO: Add specific errors as to why command failed.
    except Exception as e:
        app.logger.error("Execution failed: {}".format(str(e)))
        return jsonify({"status": "ERROR", "message": str(e)})

    # Add request and update task to database
    try:
        app.logger.debug("Logging request...")
        _log_request(user_id, post_req, task_res, 'EXECUTE', 'CMD')

    except psycopg2.Error as e:
        app.logger.error(e.pgerror)
        return jsonify({'status': 'ERROR', 'message': str(e.pgerror)})
    return jsonify(job)




@automate.route("/<task_uuid>/result", methods=['GET'])
def result(task_uuid):
    """Check the result of a task.

    Parameters
    ----------
    task_uuid : str
        The task uuid to look up

    Returns
    -------
    json
        The result of the task
    """

    # TODO merge this with status and return a details branch when a result exists.

    user_id, user_name, short_name = _get_user(request.headers)

    conn, cur = _get_db_connection()

    try:
        result = None
        cur.execute("SELECT result FROM results WHERE task_id = '%s'" % task_uuid)
        rows = cur.fetchall()
        app.logger.debug("Num rows w/ matching UUID: ".format(rows))
        for r in rows:
            result = r['result']
        res = {'result': pickle.loads(base64.b64decode(result.encode()))}
        app.logger.debugt("Result Response: {}".format(str(res)))
        return json.dumps(res)

    except Exception as e:
        app.logger.error(e)
        return json.dumps({'InternalError': e})

@automate.route("/<task_uuid>/status", methods=['GET'])
def status(task_uuid):
    """Check the status of a task.

    Parameters
    ----------
    task_uuid : str
        The task uuid to look up

    Returns
    -------
    json
        The status of the task
    """

    user_id, user_name, short_name = _get_user(request.headers)

    conn, cur = _get_db_connection()
    try:
        task_status = None
        cur.execute("SELECT * from tasks where uuid = '%s'" % task_uuid)
        rows = cur.fetchall()
        app.logger.debug("Num rows w/ matching UUID: ".format(rows))
        for r in rows:
            app.logger.debug(r)
            task_status = r['status']

        res = {'status': task_status}
        details = None
        if task_status == "SUCCEEDED":
            details = result(task_uuid)
        print("Status Response: {}".format(str(res)))        
        now = datetime.now(tz=timezone.utc)
        #body = req["body"]
        # Generate an action_id for this instance of the action:
        default_release_after = timedelta(days=30)
        job = {
            "details":details,
            "status": task_status,
            "action_id": task_uuid,
            # Default these to the principals of whoever is running this action:
            #"manage_by": request.auth.identities,
            #"monitor_by": request.auth.identities,
            #"creator_id": request.auth.effective_identity,
            "release_after": 'P30D' #default_release_after,
        }
        print(str(job))
        return json.dumps(job)

    except Exception as e:
        app.logger.error(e)
        return json.dumps({'InternalError': e})
