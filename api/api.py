
import psycopg2.extras
import pickle
import uuid
import json
import time
import statistics

from .utils import (_get_user, _create_task, _update_task, _log_request, 
                    _register_site, _register_function,  _get_zmq_servers, _resolve_endpoint,
                    _resolve_function)
from flask import current_app as app, Blueprint, jsonify, request, abort
from config import _get_db_connection
from utils.majordomo_client import ZMQClient

import threading

# Flask
api = Blueprint("api", __name__)

zmq_client = ZMQClient("tcp://localhost:50001")


# def async_request(input_obj):
#     print('sending data to zmq')
#     zmq_server.request(input_obj)


user_cache = {}
function_cache = {}
endpoint_cache = {}

caching = True


def async_funcx(task_uuid):
    
    _update_task(task_uuid, "COMPLETED")

@api.route('/test/')
def test_me():

    x = _resolve_endpoint(3, 'zz', status='ONLINE')
    app.logger.debug(x)
    return x


@api.route('/execute', methods=['POST'])
def execute():
    
    app.logger.debug("MADE IT TO EXECUTE")
    
    # Check to see if user in cache. OTHERWISE go get her!
    # Note: if user==cat, ZZ will likely want to eliminate it.
    
    user_id = 2
    user_name = "skluzacek@uchicago.edu"
    short_name = "skluzacek_uchicago"
    #user_name = 'zhuozhao@uchicago.edu'
    #short_name = 'zhuozhao_uchicago' 

    #user_name = _introspect_token(request.headers)
    #print("User name: {}".format(user_name))

    #if caching and user_name in cache:
    #    print("Getting user_id FROM CACHE")
    #    user_id, short_name = user_cache[user_name]

    #else:
    #    print("NOT IN CACHE -- fetching user from DB")
        # TODO: Need to parse user_id from headers first...
        
    #    user_id, user_name, short_name = _get_user(request.headers)
    #    if caching:
    #        user_cache[user_name] = (user_id, short_name)

    t1 = time.time()


    try:
        post_req = request.json
        print(type(post_req))
        print(post_req.keys())

        endpoint = post_req['endpoint']
        function_name = post_req['func']
        is_async = post_req['is_async']
        input_data = post_req['data']

        # Check to see if function in cache. OTHERWISE go get it. 
        # TODO: Cache flushing -- do LRU or something.
        # TODO: Move this to the RESOLVE function (not here).
        if caching and function_name in function_cache:
            # print("GETTING Func FROM CACHE!")
            func_code, func_entry = function_cache[function_name]
        else:
            # print("NOT IN CACHE -- Fetch from DB")
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

    template = None
    #if 'template' in post_req:
    #    template = post_req["template"]
    task_uuid = str(uuid.uuid4())
    print(task_uuid)
    
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
            print("Processing async request...")
            task_status = "PENDING"
            thd = threading.Thread(target=zmq_client.send, args=(endpoint_id, obj))
            res = task_uuid
            thd.start()
        else:
            print("Processing sync request...")
            res = zmq_client.send(endpoint_id, obj)
            res = pickle.loads(res)
            task_status = "SUCCESSFUL"

    # Minor TODO: Add specific errors as to why command failed.
    except Exception as e:
        print("Execution failed: {}".format(str(e)))
        return jsonify({"status": "ERROR", "message": str(e)})

    # Add request and update task to database
    try:
        print("Logging request")
        _update_task(task_uuid, task_status)
        _log_request(user_id, post_req, task_res, 'EXECUTE', 'CMD')

    except psycopg2.Error as e:
        print(e.pgerror)
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
        print(rows)
        for r in rows:
            print(r)
            task_status = r['status']

        res = {'status': task_status}
        print("Status Response: {}".format(str(res)))
        return json.dumps(res)

    except Exception as e:
        print(e)
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

