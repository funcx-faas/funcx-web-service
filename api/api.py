import psycopg2.extras
import pickle
import uuid
import json
import time
import statistics
import base64

from .utils import (_get_user, _create_task, _update_task, _log_request, 
                    _register_site, _register_function, _resolve_endpoint,
                    _resolve_function, _introspect_token, _get_container)
from flask import current_app as app, Blueprint, jsonify, request, abort
from config import _get_db_connection
from utils.majordomo_client import ZMQClient

import threading

# Flask
api = Blueprint("api", __name__)

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
    print("the result in async mode: {}".format(res))
    _update_task(task_uuid, "SUCCESSFUL", result=res)


@api.route('/execute', methods=['POST'])
def execute():
    """Execute the specified function

    Returns
    -------
    json
        The task document
    """
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
    task_status = "PENDING"
    task_res = _create_task(user_id, task_uuid, is_async, task_status)

    if 'action_id' in post_req:
        task_uuid = post_req['action_id']
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
            task_status = "PENDING"
            thd = threading.Thread(target=async_funcx, args=(task_uuid, endpoint_id, obj))
            res = task_uuid
            thd.start()
        else:
            app.logger.debug("Processing sync request...")
            res = zmq_client.send(endpoint_id, obj)
            res = pickle.loads(res)
            task_status = "SUCCESSFUL"
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
    return jsonify(res)


@api.route("/<task_uuid>/status", methods=['GET'])
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
        cur.execute("select tasks.*, results.result from tasks, results where tasks.uuid = %s and tasks.uuid = results.task_id;", (task_uuid,))
        rows = cur.fetchall()
        app.logger.debug("Num rows w/ matching UUID: ".format(rows))
        for r in rows:
            app.logger.debug(r)
            task_status = r['status']
            try:
                task_result = r['result']
            except:
                pass
        
        res = {'status': task_status}
        if task_result:
            res.update({'details': {'result': pickle.loads(base64.b64decode(task_result.encode()))}})

        print("Status Response: {}".format(str(res)))
        return json.dumps(res)

    except Exception as e:
        app.logger.error(e)
        return json.dumps({'InternalError': e})


@api.route("/<task_uuid>/result", methods=['GET'])
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

