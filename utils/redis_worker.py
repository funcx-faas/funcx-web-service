import psycopg2.extras
import threading
import pickle
import uuid
import json
import time


# TODO: yikes, lets fix this..
import os,sys,inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir) 

from utils.majordomo_client import ZMQClient
from config import _get_redis_client, _get_db_connection

from api.utils import _resolve_function, _resolve_endpoint, _create_task

from zmq.error import ZMQError


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
        zmq_client = ZMQClient("tcp://3.88.81.131:50001")

        # Get the task
        task = json.loads(rc.get(f"task:{task_id}"))

        # Check to see if function in cache. OTHERWISE go get it.
        # TODO: Cache flushing -- do LRU or something.
        # TODO: Move this to the RESOLVE function (not here).
        if caching and task['function_id'] in function_cache:
            func_code, func_entry = function_cache[task['function_id']]
        else:
            func_code, func_entry = _resolve_function(task['user_id'], task['function_id'])

            # Now put it INTO the cache!
            if caching:
                function_cache[task['function_id']] = (func_code, func_entry)

        endpoint_id = _resolve_endpoint(task['user_id'], task['endpoint_id'], status='ONLINE')

        if endpoint_id is None:
            task['status'] = 'FAILED'
            task['reason'] = "Unable to access endpoint"
            task['modified_at'] = time.time()
            rc.set(f"task:{task_id}", json.dumps(task))
            _create_task(task)
            return

        # Wrap up an object to send to ZMQ
        exec_flag = 1
        event = {'data': task['input_data'], 'context': {}}
        data = {"function": func_code, "entry_point": func_entry, 'event': event}
        obj = (exec_flag, task_id, data)
        # Send the request to ZMQ
        res = zmq_client.send(endpoint_id, obj)
        res = pickle.loads(res)
        # Set the reply on redis
        print(f"res: {res}")
        task['status'] = "SUCCEEDED"
        task['result'] = res

    # Minor TODO: Add specific errors as to why command failed.
    except ZMQError as ze:
        # Retry a task if this is what happened
        print("Caught a ZMQ error")
        if 'modified_at' in task:
            print("failing due to retry")
            # We have already retried this, so lets just fail
            task['status'] = 'FAILED'
            task['reason'] = str(ze)
        else:
            print("Trying again!")
            rc.rpush("task_list", task_id)
    except Exception as e:
        task['status'] = 'FAILED'
        task['reason'] = str(e)
    task['modified_at'] = time.time()
    print(task)
    rc.set(f"task:{task_id}", json.dumps(task))
    _create_task(task)

def main():
    """Pull tasks from the redis queue and start threads to process them"""

    while True:
        try:
            rc = _get_redis_client()
            task_id = rc.blpop("task_list")[1]
            # Put this into another list? Move it between lists?
            thd = threading.Thread(target=worker, args=(task_id, rc))
            thd.start()

        except Exception as e:
            print(e)


if __name__ == '__main__':
    main()
