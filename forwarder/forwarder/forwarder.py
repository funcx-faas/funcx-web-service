import logging
import threading
from functools import partial
import uuid
import os
import queue
import time
import zmq
import pickle

from multiprocessing import Queue
from parsl.providers import LocalProvider
from parsl.channels import LocalChannel
from parsl.app.errors import RemoteExceptionWrapper

from funcx.executors import HighThroughputExecutor as HTEX
from funcx.serialize import FuncXSerializer

from multiprocessing import Process
from forwarder.queues import RedisQueue


from forwarder import set_file_logger


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

    def __init__(self, task_q, result_q, executor, endpoint_id,
                 logdir="forwarder_logs", logging_level=logging.INFO):
        """
        Params:
             task_q : A queue object
                Any queue object that has get primitives. This must be a thread-safe queue.

             result_q : A queue object
                Any queue object that has put primitives. This must be a thread-safe queue.

             executor: Executor object
                Executor to which tasks are to be forwarded

             endpoint_id: str
                Usually a uuid4 as string that identifies the executor

             logdir: str
                Path to logdir

             logging_level : int
                Logging level as defined in the logging module. Default: logging.INFO (20)

        """
        super().__init__()
        self.logdir = logdir
        os.makedirs(self.logdir, exist_ok=True)

        global logger
        logger = set_file_logger(os.path.join(self.logdir, "forwarder.{}.log".format(endpoint_id)),
                                 level=logging_level)

        logger.info("Initializing forwarder for endpoint:{}".format(endpoint_id))
        logger.info("Log level set to {}".format(loglevels[logging_level]))
        self.task_q = task_q
        self.result_q = result_q
        self.executor = executor
        self.endpoint_id = endpoint_id
        self.internal_q = Queue()
        self.client_ports = None
        self.fx_serializer = FuncXSerializer()

    def handle_app_update(self, task_id, future):
        """ Triggered when the executor sees a task complete.

        This can be further optimized at the executor level, where we trigger this
        or a similar function when we see a results item inbound from the interchange.
        """
        logger.debug(f"[RESULTS] Updating result for {task_id}")
        try:
            res = future.result()
            self.result_q.put(task_id, {'result': res, 'completion_t': time.time()})
        except Exception as e:
            logger.debug("Task:{} failed".format(task_id))
            # Todo : Since we caught an exception, we should wrap it here, and send it
            # back onto the results queue.
        else:
            logger.debug("Task:{} succeeded".format(task_id))

    def task_loop(self):
        """ Task Loop

        The assumption is that we enter the task loop only once an endpoint is online.
        We expect the situation where the endpoint dies and reconnects to be infrequent.
        When it does go offline, the submit call will raise a zmq.error.Again which will
        cause the task to be pushed back into the queue, and the task_loop to break.
        """

        logger.info("[TASKS] Entering task loop")
        while True:

            # Get a task
            try:
                task_id, task_info = self.task_q.get(timeout=10)  # Timeout in seconds
                logger.debug("[TASKS] Got task_id {}".format(task_id))

            except queue.Empty:
                # This exception catching isn't very general,
                # Essentially any timeout exception should be caught and ignored
                logger.debug("[TASKS] Task queue:{} is empty".format(self.task_q))
                #*********************************
                # WARNING . DO NOT SKIP CONTINUE.
                # Skipping only for debugging
                #*********************************
                continue

            except Exception:
                logger.exception("[TASKS] Task queue get error")
                continue


            logger.debug("Task_info block :{}".format(task_info))

            # Convert the payload to bytes
            full_payload = task_info.encode()

            try:
                logger.debug("Submitting task to executor")
                fu = self.executor.submit(full_payload, task_id=task_id)

            except zmq.error.Again:
                logger.exception(f"[TASKS] Endpoint busy/unavailable, could not forward task:{task_id}")
                self.task_q.put(task_id, task_info)
                logger.warning("[TASKS] Breaking task-loop to switch to endpoint liveness loop")
                break
            except Exception:
                # Broad catch to avoid repeating the task reput,
                logger.exception("[TASKS] Some unhandled error occurred")
                self.task_q.put(task_id, task_info)

            # Task is now submitted. Tack a callback on that.
            fu.add_done_callback(partial(self.handle_app_update, task_id))


    def run(self):
        """ Process entry point.
        """
        logger.info("[MAIN] Loop starting")
        logger.info("[MAIN] Executor: {}".format(self.executor))

        try:
            self.task_q.connect()
            self.result_q.connect()
        except Exception:
            logger.exception("Connecting to the queues have failed")

        self.executor.start()
        conn_info = self.executor.connection_info
        self.internal_q.put(conn_info)
        logger.info("[MAIN] Endpoint connection info: {}".format(conn_info))

        # Start the task loop
        while True:
            logger.info("[MAIN] Waiting for endpoint to connect")
            self.executor.wait_for_endpoint()
            logger.info("[MAIN] Endpoint is now online")
            self.task_loop()

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
                    executor=None,
                    task_q=None,
                    result_q=None,
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
        task_q = RedisQueue('task_{}'.format(endpoint_id), redis_address)
    if not result_q:
        # result_q = RedisQueue('result_{}'.format(endpoint_id), redis_address)
        # Change of design. We want all tasks to go to a results table and results_list queue
        # This would allow any frontend service to access the results stream.
        result_q = RedisQueue('results', redis_address)

    print("Logging_level: {}".format(logging_level))
    print("Task_q: {}".format(task_q))
    print("Result_q: {}".format(result_q))

    if not executor:
        executor = HTEX(label='htex',
                        provider=LocalProvider(
                            channel=LocalChannel),
                        address=address)

    fw = Forwarder(task_q, result_q, executor,
                   "Endpoint_{}".format(endpoint_id),
                   logging_level=logging_level)
    fw.start()
    return fw


if __name__ == "__main__":

    pass
    # test()
