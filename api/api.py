
import psycopg2.extras
import pickle
import uuid
import json
import time
import statistics

from .utils import (_get_user, _create_task, _log_request, 
                    _register_site, _register_function,  _get_zmq_servers, _resolve_endpoint,
                    _resolve_function)
from flask import current_app as app, Blueprint, jsonify, request, abort
from config import _get_db_connection
from utils.majordomo_client import ZMQClient



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

net_webservice_times = []
request_times = []

@api.route('/test/')
def test_me():

    x = _resolve_endpoint(3, 'zz', status='ONLINE')
    app.logger.debug(x)
    return x


@api.route('/execute', methods=['POST'])
def execute():



    t0 = time.time()
    app.logger.debug("MADE IT TO EXECUTE")
    
    # Check to see if user in cache. OTHERWISE go get her!
    # Note: if user==cat, ZZ will likely want to eliminate it.
    
    user_id = 2
    user_name = "skluzacek@uchicago.edu"
    short_name = "skluzacek_uchicago"

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

    # print("Time to get user: {}".format(t1-t0))

    try:
        # app.logger.debug(request.json)

        post_req = ""
        post_req = request.json
        endpoint = post_req['endpoint']
        function_name = post_req['func']
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


        # print("func_code: {}".format(func_code))
        endpoint_id = _resolve_endpoint(user_id, endpoint, status='ONLINE')
        if endpoint_id is None:
            return jsonify({"status": "ERROR", "message": str("Invalid endpoint")})
        # print("endpoint id {}".format(endpoint_id))
    except Exception as e:
        app.logger.error(e)

    t2 = time.time()
    # print("Time to resolve endpoint and func: {}".format(t2-t1))

    app.logger.debug("POST_REQUEST:" + str(post_req))
    try:
        pass
        # print('checking async')
        # is_async = post_req["async"]
    except KeyError:
        print("THERE's an error...")
        # is_async = False
	#         return jsonify({"status": "Error", "message": "Missing 'async' argument set to 'True' or 'False'."})
    # print('async: {}'.format(is_async))

    # print('overriding async')
    is_async = False

    template = None
    #if 'template' in post_req:
    #    template = post_req["template"]
    task_uuid = str(uuid.uuid4())

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
        # print("Running command: {}".format(obj))
        request_start = time.time()
        if is_async:
            pass
            # print('starting thread to serve request')
            # try:
            #     processThread = threading.Thread(target=async_request, args=(pickle.dumps(obj),))
            #     processThread.start()
            # except Exception as e:
            #     print('threading error: {}'.format(e))
            # response = task_uuid
        else:
            # print("Putting on execution queue")
            res = zmq_client.send(endpoint_id, obj)
            res = pickle.loads(res)
            # print(res)
            # response = pickle.loads(res.result())
        request_end = time.time()

    # Minor TODO: Add specific errors as to why command failed.
    except Exception as e:
        print("Execution failed: {}".format(str(e)))
        return jsonify({"status": "ERROR", "message": str(e)})

    # Add request and task to database
    try:
        task_res = _create_task(user_id, task_uuid, is_async)
        _log_request(user_id, post_req, task_res, 'EXECUTE', 'CMD')

    except psycopg2.Error as e:
        print(e.pgerror)
        return jsonify({'status': 'ERROR', 'message': str(e.pgerror)})

    # print("Task Submission Status: {}".format(str(task_res)))

    # Return task_submission response.
    t3 = time.time()

    net_webservice_times.append((t3-t0)-(request_end-request_start))
    request_times.append(request_end - request_start)
        
    if True is True:

        # print("Web Service RoundTrip: {}".format(t3-t0))
        print("Request Time: {}".format(statistics.mean(net_webservice_times)))
        print("Net Web Service Latency: {}".format(statistics.mean(request_times)))
    # counter += 1
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



# threads = []
#
# def multi_thread_launch(thread_id, task_id, cmd, is_async):
#     # Create new threads
#     thread2 = ParslThread(thread_id, task_id, cmd, is_async)
#
#     # Start new Threads
#     thread2.start()
#
#     # Add threads to thread list
#     threads.append(thread2)
