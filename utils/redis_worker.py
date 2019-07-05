import psycopg2.extras
import threading
import pickle
import uuid
import json
import time

from utils.majordomo_client import ZMQClient

from config import _get_redis_client, _get_db_connection

caching = True

function_cache = {}
endpoint_cache = {}

def worker(task_id, rc):
    """Process the task and invoke the execution

    Parameters
    ----------
    task_id : str
        The uuid of the task
    rc : RedisClient
        The client to interact with redis
    """
    try:
        # Get the task
        task = json.loads(rc.get(task_id))

        # task {
        # endpoint_id,
        # function_id,
        # input_data,
        # user_name,
        # user_id,
        # status }

        # Check to see if function in cache. OTHERWISE go get it.
        # TODO: Cache flushing -- do LRU or something.
        # TODO: Move this to the RESOLVE function (not here).
        if caching and task['function_id'] in function_cache:
            app.logger.debug("Fetching function from function cache...")
            func_code, func_entry = function_cache[task['function_id']]
        else:
            app.logger.debug("Function name not in cache -- fetching from DB...")
            func_code, func_entry = _resolve_function(task['user_'], task['function_id'])

            # Now put it INTO the cache!
            if caching:
                function_cache[task['function_id']] = (func_code, func_entry)

        endpoint_id = _resolve_endpoint(task['user_id'], task['endpoint_id'], status='ONLINE')

        if endpoint_id is None:
            task['status'] = 'FAILED'
            task['reason'] = "Unable to access endpoint"
            rc.set(task_id, json.dumps(task))

        # Wrap up an object to send to ZMQ
        exec_flag = 1
        event = {'data': task['input_data'], 'context': {}}
        data = {"function": func_code, "entry_point": func_entry, 'event': event}
        obj = (exec_flag, task_id, data)

        # Send the request to ZMQ
        res = zmq_client.send(endpoint_id, obj)
        res = pickle.loads(res)

        # Set the reply on redis
        task['status'] = "SUCCEEDED"
        task['result'] = res

    # Minor TODO: Add specific errors as to why command failed.
    except Exception as e:
        app.logger.error("Execution failed: {}".format(str(e)))
        task['status'] = 'FAILED'
        task['reason'] = str(e)

    rc.set(task_id, json.dumps(task))


def main():
    """Pull tasks from the redis queue and start threads to process them"""

    while True:
        try:
            rc = _get_redis_client()
            task_id = rc.blpop("task_list")
            print(task_id)
            # Put this into another list? Move it between lists?

            thd = threading.Thread(target=worker, args=(task_id, rc))
            thd.start()

        except Exception as e:
            print(e)


if __name__ == '__main__':
    main()
