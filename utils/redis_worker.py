# A worker for redis


caching = True

function_cache = {}
endpoint_cache = {}

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


def work():




    # Get the user_id
    if caching and user_name in user_cache:
        app.logger.debug("Getting user_id FROM CACHE")
        user_id, short_name = user_cache[user_name]

    else:
        app.logger.debug("User ID not in cache -- fetching from DB")
        user_id, user_name, short_name = _get_user(request.headers)
        if caching:
            user_cache[user_name] = (user_id, short_name)

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

    # Create task entry in DB with status "PENDING"
    task_status = "PENDING"
    task_res = _create_task(user_id, task_uuid, is_async, task_status)

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


    # DB status:
    cur.execute("select tasks.*, results.result from tasks, results where tasks.uuid = %s and tasks.uuid = "
                "results.task_id;", (task_uuid,))
    rows = cur.fetchall()
    app.logger.debug("Num rows w/ matching UUID: ".format(rows))
    for r in rows:
        app.logger.debug(r)
        task_status = r['status']
        try:
            task_result = r['result']
        except:
            pass

        if task_result:
            res.update({'details': {'result': pickle.loads(base64.b64decode(task_result.encode()))}})