import redis
import queue

from forwarder.queues.base import FuncxQueue, NotConnected
import json


class RedisQueue(FuncxQueue):
    """ A basic redis queue

    The queue only connects when the `connect` method is called to avoid
    issues with passing an object across processes.

    Parameters
    ----------

    hostname : str
       Hostname of the redis server

    port : int
       Port at which the redis server can be reached. Default: 6379

    """

    def __init__(self, prefix, hostname, port=6379):
        """ Initialize
        """
        self.hostname = hostname
        self.port = port
        self.redis_client = None
        self.prefix = prefix

    def connect(self):
        """ Connects to the Redis server
        """
        try:
            if not self.redis_client:
                self.redis_client = redis.StrictRedis(host=self.hostname, port=self.port, decode_responses=True)
        except redis.exceptions.ConnectionError:
            print("ConnectionError while trying to connect to Redis@{}:{}".format(self.hostname,
                                                                                  self.port))

            raise

    def get(self, kind, timeout=1):
        """ Get an item from the redis queue

        Parameters
        ----------
        kind : str
           Required. The kind of item to fetch from the DB

        timeout : int
           Timeout for the blocking get in seconds
        """
        try:
            x = self.redis_client.blpop(f'{self.prefix}_list', timeout=timeout)
            if not x:
                raise queue.Empty

            task_list, task_id = x
            jtask_info = self.redis_client.hget(f'task_{task_id}', kind)
            task_info = json.loads(jtask_info)
        except queue.Empty:
            raise

        except AttributeError:
            raise NotConnected(self)

        except redis.exceptions.ConnectionError:
            print(f"ConnectionError while trying to connect to Redis@{self.hostname}:{self.port}")
            raise

        return task_id, task_info

    def put(self, key, kind, payload):
        """ Put's the key:payload into a dict and pushes the key onto a queue
        Parameters
        ----------
        key : str
            The task_id to be pushed

        kind : str
            The type of payload

        payload : dict
            Dict of task information to be stored
        """
        try:
            self.redis_client.hset(f'task_{key}', kind, json.dumps(payload))
            self.redis_client.rpush(f'{self.prefix}_list', key)
        except AttributeError:
            raise NotConnected(self)
        except redis.exceptions.ConnectionError:
            print("ConnectionError while trying to connect to Redis@{}:{}".format(self.hostname,
                                                                                  self.port))
            raise

    @property
    def is_connected(self):
        return self.redis_client is not None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "<RedisQueue at {}:{}#{}".format(self.hostname, self.port, self.prefix)


def test():
    rq = RedisQueue('task', '127.0.0.1')
    rq.connect()
    rq.put("01", {'a': 1, 'b': 2})
    res = rq.get(timeout=1)
    print("Result : ", res)


if __name__ == '__main__':
    test()
