import psycopg2.extras
import threading
import pickle
import parsl
import uuid
import json
import time


from .utils import _get_user, _create_task, _log_request, _register_site, _get_zmq_servers
from flask import current_app as app, Blueprint, jsonify, request, abort
from config import _get_db_connection, cooley_config
from parsl.app.app import python_app

from utils.zmq_server import ZMQServer

# Flask
api = Blueprint("api", __name__)

zmq_server = ZMQServer()

zmq_servers = _get_zmq_servers()

#def async_request(input_obj):
    # print('sending data to zmq')
    # zmq_server.request(input_obj)


@api.route('/execute', methods=['POST'])
def execute():

    app.logger.debug("MADE IT TO EXECUTE")
    user_id, user_name, short_name = _get_user(request.headers)

    #if request.headers is not None:
        #user_id, user_name, short_name = 1, "skluzacek@uchicago.edu", "skluzacek"
    # if not user_name:
    #     abort(400, description="Error: You must be logged in to perform this function.")

    # Retrieve user-submitted BASH command and path to data.
    try:
        app.logger.debug(request.json)

        post_req = ""
        if "data" in (request.json).keys():
            post_req = request.json["data"]
        else:
            post_req = json.loads(request.json)
    except Exception as e:
        app.logger.error(e)
    try:
        post_req = json.loads(request.json)
    except:
        pass

    print("POST_REQUEST:" + str(post_req))
    try:
        print('checking async')
        # is_async = post_req["async"]
    except KeyError:
        print("THERE's an error...")
        # is_async = False
	#         return jsonify({"status": "Error", "message": "Missing 'async' argument set to 'True' or 'False'."})
    # print('async: {}'.format(is_async))
    try:
        print(post_req)
        if 'cmd' in post_req:
            cmd = post_req["cmd"]
        elif 'command' in post_req:
            cmd = post_req['command']
    except Exception as e:
        return jsonify({"error": str(e)})
    print(cmd)
    print("Processing Command: ".format(cmd))


    print('overriding async')
    is_async = False


    template = None
    #if 'template' in post_req:
    #    template = post_req["template"]
    task_uuid = str(uuid.uuid4())

    if 'action_id' in post_req:
        task_uuid = post_req['action_id']

    if template:
        cmd = cmd.format(**template)

    try:
        # Spin off thread to communicate with Parsl service.
        # multi_thread_launch("parsl-thread", str(task_uuid), cmd, is_async)

        exec_flag = 1
        # Future proofing for other exec types
        data = {"command": cmd}
        # Set the exec site
        site = "local"
        obj = (exec_flag, task_uuid, data)
        print("Running command: {}".format(obj))
        request_start = time.time()
        if is_async:
            print('starting thread to serve request')
            try:
                processThread = threading.Thread(target=async_request, args=(pickle.dumps(obj),))
                processThread.start()
            except Exception as e:
                print('threading error: {}'.format(e))
            response = task_uuid
        else:
            print("INIT TASK EXECUTION")
            #res = execute_task(obj)
            #print(res)
            #print("FINISHED TASK EXECUTION")
            #print(res.done())
            res = zmq_server.request(pickle.dumps(obj))
            response = pickle.loads(res.result())
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

    print("Task Submission Status: {}".format(str(task_res)))

    # Return task_submission response.
    return jsonify(task_res)


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
    sitename = None
    description = None
    try:
        sitename = request.json["endpoint_name"]
        description = request.json["description"]
    except Exception as e:
        app.logger.error(e)
    app.logger.debug(sitename)
    port_num = _register_site(user_id, sitename, description)
    return jsonify({'port': int(port_num)})


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
