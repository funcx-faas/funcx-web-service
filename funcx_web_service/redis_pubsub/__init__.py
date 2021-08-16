import logging
import queue
from typing import Tuple

import redis
from redis.exceptions import ConnectionError

from .tasks import Task, TaskState

logger = logging.getLogger(__name__)


class NotConnected(Exception):
    """Queue is not connected/active"""

    def __init__(self, queue):
        self.queue = queue

    def __str__(self):
        return "Queue {} is not connected. Cannot execute queue operations".format(
            self.queue
        )


class RedisPubSub(object):
    def __init__(self, hostname: str, port: int = 6379):
        self.hostname = hostname
        self.port = port
        self.subscriber_count = 0
        self.redis_client = None
        self.pubsub = None
        self.task_channel_prefix = "task_channel_"
        self._task_channel_prefix_len = len(self.task_channel_prefix)
        self.task_queue_prefix = "task_queue_"

    def channel_name(self, endpoint_id):
        return f"{self.task_channel_prefix}{endpoint_id}"

    def queue_name(self, endpoint_id):
        return f"{self.task_queue_prefix}{endpoint_id}"

    def connect(self):
        try:
            self.redis_client = redis.StrictRedis(
                host=self.hostname, port=self.port, decode_responses=True
            )
            self.redis_client.ping()
        except ConnectionError:
            logger.exception(
                "ConnectionError while trying to connect to Redis@{}:{}".format(
                    self.hostname, self.port
                )
            )
            raise
        self.pubsub = self.redis_client.pubsub()

    def put(self, endpoint_id, task):
        """Put the task object into the channel for the endpoint"""
        try:
            task.endpoint = endpoint_id
            task.status = TaskState.WAITING_FOR_EP
            # Note: Task object is already in Redis
            subscribers = self.redis_client.publish(
                self.channel_name(endpoint_id), task.task_id
            )
            if subscribers == 0:
                self.redis_client.rpush(self.queue_name(endpoint_id), task.task_id)

        except AttributeError:
            raise NotConnected(self)

        except ConnectionError:
            logger.exception(
                "ConnectionError while trying to connect to Redis@{}:{}".format(
                    self.hostname, self.port
                )
            )
            raise

    def republish_from_queue(self, endpoint_id):
        """Tasks pushed to Redis pubsub channels might have gone unreceived.
        When a new endpoint registers, it should republish tasks from it's queues
        to the pubsub channels.
        """
        while True:
            try:
                x = self.redis_client.blpop(self.queue_name(endpoint_id), timeout=1)
                if not x:
                    break
                task_list, task_id = x
                self.redis_client.publish(self.channel_name(endpoint_id), task_id)
            except AttributeError:
                logger.exception("Failure while republishing from queue to pubsub")
                raise NotConnected(self)

            except redis.exceptions.ConnectionError:
                logger.exception("Failure while republishing from queue to pubsub")
                raise

    def subscribe(self, endpoint_id):
        logger.info(f"Subscribing to tasks_{endpoint_id}")
        self.pubsub.subscribe(self.channel_name(endpoint_id))
        self.republish_from_queue(endpoint_id)
        self.subscriber_count += 1

    def unsubscribe(self, endpoint_id):
        self.pubsub.unsubscribe(self.channel_name(endpoint_id))
        if self.subscriber_count > 0:
            self.subscriber_count -= 1

    def get(self, timeout: int = 2) -> Tuple[str, Task]:
        """
        Parameters
        ----------

        timeout : int
             milliseconds to wait
        """
        if self.subscriber_count < 1:
            raise queue.Empty

        timeout_s = timeout / 1000
        try:
            package = self.pubsub.get_message(
                ignore_subscribe_messages=True, timeout=timeout_s
            )
            if not package:
                raise queue.Empty("Channels empty")
            # Strip channel prefix
            dest_endpoint = package["channel"][self._task_channel_prefix_len :]
            task_id = package["data"]
            task = Task.from_id(self.redis_client, task_id)

        except queue.Empty:
            raise

        except AttributeError:
            raise NotConnected(self)

        except ConnectionError:
            logger.exception(
                f"ConnectionError while trying to connect to Redis@{self.hostname}:{self.port}"
            )
            raise

        except Exception:
            logger.exception("Uncaught exception")
            raise

        return dest_endpoint, task
