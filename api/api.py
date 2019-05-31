
import psycopg2.extras
import pickle
import uuid
import json
import time
import statistics

from .utils import (_get_user, _create_task, _update_task, _log_request, 
                    _register_site, _register_function,  _get_zmq_servers, _resolve_endpoint,
                    _resolve_function, _introspect_token)
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
    """
    Run the function async and update the database.

    :param task_uuid:
    :param endpoint_id:
    :param obj:
    :return:
    """
    _update_task(task_uuid, "RUNNING")
    res = zmq_client.send(endpoint_id, obj)
    _update_task(task_uuid, "SUCCESSFUL", result=res)


# TODO: Clean this up. 
@api.route('/test/')
def test_me():

    x = _resolve_endpoint(3, 'zz', status='ONLINE')
    app.logger.debug(x)
    return x


@api.route('/execute', methods=['POST'])
def execute():
    
    app.logger.debug("Executing function...")
    
    # Check to see if user in cache. OTHERWISE go get her!
    # Note: if user==cat, ZZ will likely want to eliminate it.

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
        function_name = post_req['func']
        is_async = post_req['is_async']
        input_data = post_req['data']

        # Check to see if function in cache. OTHERWISE go get it. 
        # TODO: Cache flushing -- do LRU or something.
        # TODO: Move this to the RESOLVE function (not here).
        if caching and function_name in function_cache:
            app.logger.debug("Fetching function from function cache...")
            func_code, func_entry = function_cache[function_name]
        else:
            app.logger.debug("Function name not in cache -- fetching from DB...")
            func_code, func_entry = _resolve_function(user_id, function_name)
            
            # Now put it INTO the cache! 
            if caching:
                function_cache[function_name] = (func_code, func_entry)


        endpoint_id = _resolve_endpoint(user_id, endpoint, status='ONLINE')
        if endpoint_id is None:
            return jsonify({"status": "ERROR", "message": str("Invalid endpoint")})
    except Exception as e:
        app.logger.error(e)

    app.logger.debug("POST_REQUEST:" + str(post_req))

    # TODO: Do we still plan on doing template stuff? If not, we should remove. 
    template = None
    #if 'template' in post_req:
    #    template = post_req["template"]
    task_uuid = str(uuid.uuid4())
    app.logger.info("Task assigned UUID: ".format(task_uuid))
    
    # Create task entry in DB with status "PENDING"
    task_status = "PENDING"
    task_res = _create_task(user_id, task_uuid, is_async, task_status)


    if 'action_id' in post_req:
        task_uuid = post_req['action_id']

    cmd = 'echo'
    if template:
        cmd = cmd.format(**template)

    try:
        # Spin off thread to communicate with Parsl service.
        # multi_thread_launch("parsl-thread", str(task_uuid), cmd, is_async)

        exec_flag = 1
        # Future proofing for other exec types

        event = {'data': input_data, 'funcx': 'hello'}

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
    """
    Check the status of a task.

    :param task_uuid:
    :return:
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
        print("Status Response: {}".format(str(res)))
        return json.dumps(res)

    except Exception as e:
        app.logger.error(e)
        return json.dumps({'InternalError': e})


@api.route("/register_endpoint", methods=['POST'])
def register_site():
    """
    Register the site. Add this site to the database and associate it with this user.

    :return: port to connect to.
    """
    user_id, user_name, short_name = _get_user(request.headers)
    if not user_name:
        abort(400, description="Error: You must be logged in to perform this function.")
    endpoint_name = None
    description = None
    try:
        endpoint_name = request.json["endpoint_name"]
        description = request.json["description"]
    except Exception as e:
        app.logger.error(e)
    app.logger.debug(endpoint_name)
    endpoint_uuid = _register_site(user_id, endpoint_name, description)
    return jsonify({'endpoint_uuid': endpoint_uuid})


@api.route("/register_function", methods=['POST'])
def register_function():
    """
    Register the function. 
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
    return jsonify({'function_name': function_name})

