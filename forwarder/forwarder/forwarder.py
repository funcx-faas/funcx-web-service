import logging
import os
import queue
import threading
import time
from functools import partial
from multiprocessing import Process
from multiprocessing import Queue

import requests
import zmq
from funcx.executors import HighThroughputExecutor as HTEX
from funcx.serialize import FuncXSerializer
from parsl.channels import LocalChannel
from parsl.providers import LocalProvider

from forwarder import set_file_logger
from forwarder.endpoint_db import EndpointDB
from forwarder.queues import RedisQueue
from forwarder.queues.redis.redis_q import EndpointQueue
from forwarder.queues.redis.tasks import Task, TaskState


def double(x):
    return x * 2


def failer(x):
    return x / 0

loglevels = {50: 'CRITICAL',
             40: 'ERROR',
             30: 'WARNING',
             20: 'INFO',
             10: 'DEBUG',
             0: 'NOTSET'}


class Forwarder(Process):
    """ Forwards tasks/results between the executor and the queues

        Tasks_Q  Results_Q
           |     ^
           |     |
           V     |
          Executors

    Todo : We need to clarify what constitutes a task that comes down
    the task pipe. Does it already have the code fragment? Or does that need to be sorted
    out from some DB ?
    """

    def __init__(self, task_q, executor, endpoint_id,
                 heartbeat_threshold=60, endpoint_addr=None,
                 redis_address=None,
                 logdir="forwarder_logs", logging_level=logging.INFO,
                 max_heartbeats_missed=2):
        """
        Parameters
        ----------
        task_q : EndpointQueue
        Any queue object that has get primitives. This must be a thread-safe queue.

        executor: Executor object
        Executor to which tasks are to be forwarded

        endpoint_id: str
        Usually a uuid4 as string that identifies the executor

        endpoint_addr: str
        Endpoint ip address as a string

        heartbeat_threshold : int
        Heartbeat threshold in seconds

        logdir: str
        Path to logdir

        logging_level : int
        Logging level as defined in the logging module. Default: logging.INFO (20)

        max_heartbeats_missed : int
        The maximum heartbeats missed before the forwarder terminates

        """
        super().__init__()
        self.logdir = logdir
        os.makedirs(self.logdir, exist_ok=True)

        global logger
        logger = logging.getLogger(endpoint_id)
        
        if len(logger.handlers) == 0:
            logger = set_file_logger(os.path.join(self.logdir, "forwarder.{}.log".format(endpoint_id)),
                                    name=endpoint_id,
                                    level=logging_level)

        logger.info("Initializing forwarder for endpoint:{}".format(endpoint_id))
        logger.info("Log level set to {}".format(loglevels[logging_level]))

        self.endpoint_addr = endpoint_addr
        self.task_q = task_q
        self.heartbeat_threshold = heartbeat_threshold
        self.executor = executor
        self.endpoint_id = endpoint_id
        self.endpoint_addr = endpoint_addr
        self.redis_address = redis_address
        self.internal_q = Queue()
        self.client_ports = None
        self.fx_serializer = FuncXSerializer()
        self.kill_event = threading.Event()
        self.max_heartbeats_missed = max_heartbeats_missed

    def handle_app_update(self, task_id, future):
        """ Triggered when the executor sees a task complete.

        This can be further optimized at the executor level, where we trigger this
        or a similar function when we see a results item inbound from the interchange.
        """

        print(f"*** TASK RETURN STARTED: {task_id} -- {time.time()} ***")
        logger.debug(f"[RESULTS] Updating result for {task_id}")
        try:
            res_dict = future.result()
            logger.info("Res_dict : {}".format(res_dict))
            task = Task.from_id(self.task_q.redis_client, task_id)

            # TODO: What does the res_dict look like?  Can we just set task.result=res_dict?
            if 'result' in res_dict:
                task.status = TaskState.SUCCESS
                task.result = {
                    'result': res_dict['result'],
                    'completion_t': time.time()
                }
            elif 'exception' in res_dict:
                task.status = TaskState.FAILED
                task.result = {
                    'exception': res_dict['exception'],
                    'completion_t': time.time()
                }

        except Exception as e:
            logger.error(f"Task update {task_id} failed due to {e}")
            # Todo : Since we caught an exception, we should wrap it here, and send it
            # back onto the results queue.
        else:
            print(f"*** TASK RETURN SUCCEEDED: {task_id} -- {time.time()}***")
            logger.info(f"Task:{task_id} succeeded")

    def heartbeat_fail(self):
        """Return true if too many heartbeats have been missed"""
        return int(time.time() - self.executor.last_response_time) > \
                    (self.max_heartbeats_missed * self.heartbeat_threshold)

    def task_loop(self):
        """ Task Loop

        The assumption is that we enter the task loop only once an endpoint is online.
        We expect the situation where the endpoint dies and reconnects to be infrequent.
        When it does go offline, the submit call will raise a zmq.error.Again which will
        cause the task to be pushed back into the queue, and the task_loop to break.
        """

        logger.info("[TASKS] Entering task loop")
        while True:
            # Check if too many heartbeats have been missed
            if self.heartbeat_fail():
                # Too many heartbeats have been missed. Set kill event
                logger.warning("[TASKS] Too many heartbeats missed. Setting kill event.")
                self.kill_event.set()
                break

            # Get a task
            try:
                task = self.task_q.dequeue(timeout=self.heartbeat_threshold)
                logger.debug(f"[TASKS] Got task_id {task.task_id}")

            except queue.Empty:
                try:
                    logger.debug("[TASKS] Requesting info")
                    self.executor.request_status_info()
                except zmq.error.Again:
                    logger.exception(f"[TASKS] Endpoint busy/unavailable, status info request failed")
                    break
                else:
                    continue

            except Exception:
                logger.exception("[TASKS] Task queue get error")
                continue

            task_payload = task.payload
            logger.debug(f"Task payload block:{task_payload}")

            # Convert the payload to bytes
            full_payload = task_payload.encode()

            # If the kill event has been set put the task back on the queue and break
            if self.kill_event.is_set():
                logger.exception(f"[TASKS] Kill event set. Putting task back in queue. task:{task.task_id}")
                self.task_q.enqueue(task)
                logger.warning("[TASKS] Breaking task-loop")
                break

            try:
                logger.debug("Submitting task to executor")
                fu = self.executor.submit(full_payload, task_id=task.task_id)
                t_fin = time.time()
                print(f"*** FINISH {task.task_id} *** {t_fin}")

            except zmq.error.Again:
                logger.exception(f"[TASKS] Endpoint busy/unavailable, could not forward task:{task.task_id}")
                self.task_q.enqueue(task)
                logger.warning("[TASKS] Breaking task-loop to switch to endpoint liveness loop")
                break
            except Exception:
                # Broad catch to avoid repeating the task reput,
                logger.exception(f"[TASKS] Some unhandled error occurred, re-queueing task={task.task_id}")
                self.task_q.enqueue(task)
            else:
                # Task is now submitted. Tack a callback on that.
                fu.add_done_callback(partial(self.handle_app_update, task.task_id))

    def update_endpoint_metadata(self):
        """ Geo locate the endpoint and push as metadata into redis
        """
        resp = requests.get('http://ipinfo.io/{}/json'.format(self.endpoint_addr))
        ep_db = EndpointDB(self.redis_address)
        ep_db.connect()
        ep_db.set_endpoint_metadata(self.endpoint_id, resp.json())
        ep_db.close()
        return resp.json()

    def run(self):
        """ Process entry point.
        """
        logger.info("[MAIN] Loop starting")
        logger.info(f"[MAIN] Executor: {self.executor}")
        logger.info(f"[MAIN] Attempting to resolve endpoint_addr: {self.endpoint_addr}")

        try:
            resp = self.update_endpoint_metadata()
        except Exception:
            logger.exception(f"Failed to geo locate {self.endpoint_addr}")
        else:
            logger.info(f"Endpoint is at {resp}")

        try:
            self.task_q.connect()
        except Exception:
            logger.exception("Connecting to the queues have failed")

        self.executor.start()
        conn_info = self.executor.connection_info
        self.internal_q.put(conn_info)
        logger.info("[MAIN] Endpoint connection info: {}".format(conn_info))

        logger.info("[MAIN] Waiting for endpoint to connect")
        self.executor.wait_for_endpoint()
        
        # Start the task loop
        while True:
            logger.info("[MAIN] Endpoint is now online")
            self.task_loop()
            # if the kill event is set, exit.
            if self.kill_event.is_set():
                logger.critical("[MAIN] Kill event set. Exiting Run loop")
                break

        logger.critical("[MAIN] Something has broken. Exiting Run loop")
        return

    @property
    def connection_info(self):
        """Get the client ports to which the interchange must connect to
        """

        if not self.client_ports:
            self.client_ports = self.internal_q.get()

        return self.client_ports


def spawn_forwarder(address,
                    redis_address,
                    endpoint_id,
                    endpoint_addr=None,
                    executor=None,
                    task_q=None,
                    logging_level=logging.INFO):
    """ Spawns a forwarder and returns the forwarder process for tracking.

    Parameters
    ----------

    address : str
       IP Address to which the endpoint must connect

    redis_address : str
       The redis host url at which task/result queues can be created. No port info

    endpoint_id : str
       Endpoint id string that will be used to address task/result queues.

    endpoint_addr : str
       Endpoint addr string that will be used to geo-locate address

    executor : Executor object. Optional
       Executor object to be instantiated.

    task_q : Queue object
       Queue object matching forwarder.queues.base.FuncxQueue interface

    logging_level : int
       Logging level as defined in the logging module. Default: logging.INFO (20)

    endpoint_id : uuid string
       Endpoint id for which the forwarder is being spawned.

    Returns:
         A Forwarder object
    """
    if not task_q:
        # task_q = RedisQueue('task_{}'.format(endpoint_id), redis_address)
        task_q = EndpointQueue(endpoint_id, redis_address)

    print("Logging_level: {}".format(logging_level))
    print("Task_q: {}".format(task_q))

    if not executor:
        executor = HTEX(label='htex',
                        provider=LocalProvider(
                            channel=LocalChannel),
                        endpoint_db=EndpointDB(redis_address),
                        endpoint_id=endpoint_id,
                        address=address)
    fw = Forwarder(task_q, executor,
                   endpoint_id,
                   endpoint_addr=endpoint_addr,
                   redis_address=redis_address,
                   logging_level=logging_level)
    fw.start()
    return fw


if __name__ == "__main__":

    pass
    # test()
