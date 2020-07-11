import redis
import queue
import uuid
import time

# from forwarder.queues.base import FuncxQueue, NotConnected
import json


class EndpointDB(object):
    """ A basic redis DB

    The queue only connects when the `connect` method is called to avoid
    issues with passing an object across processes.

    Parameters
    ----------

    endpoint_id: str
       Endpoint UUID

    hostname : str
       Hostname of the redis server

    port : int
       Port at which the redis server can be reached. Default: 6379

    """

    def __init__(self, hostname, port=6379):
        """ Initialize
        """
        self.hostname = hostname
        self.port = port
        self.redis_client = None

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

    def get(self, endpoint_id, timeout=1, last=60*4):
        """ Get an item from the redis queue

        Parameters
        ----------
        endpoint_id: str
           Endpoint UUID

        timeout : int
           Timeout for the blocking get in seconds
        """
        try:
            end = min(self.redis_client.llen(f'ep_status_{endpoint_id}'), last)
            print("Total len :", end)
            items = self.redis_client.lrange(f'ep_status_{endpoint_id}', 0, end)
            if not items:
                raise queue.Empty

        except queue.Empty:
            raise

        except AttributeError:
            raise NotConnected(self)

        except redis.exceptions.ConnectionError:
            print(f"ConnectionError while trying to connect to Redis@{self.hostname}:{self.port}")
            raise

        return items

    def set_endpoint_metadata(self, endpoint_id, json_data):
        """ Sets the endpoint metadata in a dict on redis

        Parameters
        ----------

        endpoint_id : str
        Endpoint UUID string

        json_data : {str: str}
        Endpoint metadata as json
        """
        self.redis_client.hmset('endpoint:{}'.format(endpoint_id), json_data)
        return

    def get_all(self, timeout=1):
        """ Get an item from the redis queue

        Parameters
        ----------
        endpoint_id: str
           Endpoint UUID

        timeout : int
           Timeout for the blocking get in seconds
        """
        try:
            # self.redis_client
            end = min(self.redis_client.llen(f'ep_status_{endpoint_id}'), last)
            print("Total len :", end)
            items = self.redis_client.lrange(f'ep_status_{endpoint_id}', 0, end)
            if not items:
                raise queue.Empty

        except queue.Empty:
            raise

        except AttributeError:
            raise NotConnected(self)

        except redis.exceptions.ConnectionError:
            print(f"ConnectionError while trying to connect to Redis@{self.hostname}:{self.port}")
            raise

        return items

    def put(self, endpoint_id, payload):
        """ Put's the key:payload into a dict and pushes the key onto a queue
        Parameters
        ----------
        endpoint_id: str
           Endpoint UUID

        payload : dict
            Dict of task information to be stored
        """
        payload['timestamp'] = time.time()
        try:
            # self.redis_client.set(f'{self.prefix}:{key}', json.dumps(payload))
            self.redis_client.lpush(f'ep_status_{endpoint_id}', json.dumps(payload))
            if 'new_core_hrs' in payload:
                self.redis_client.incrbyfloat('funcx_worldwide_counter', amount=payload['new_core_hrs'])
            self.redis_client.ltrim(f'ep_status_{endpoint_id}', 0, 2880) # Keep 2 x 24hr x 60 min worth of logs

        except AttributeError:
            raise NotConnected(self)
        except redis.exceptions.ConnectionError:
            print("ConnectionError while trying to connect to Redis@{}:{}".format(self.hostname, self.port))
            raise

    @property
    def is_connected(self):
        return self.redis_client is not None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return "<RedisQueue at {}:{}".format(self.hostname, self.port)

    def close(self):
        self.redis_client.connection_pool.disconnect()
        del self.redis_client


def test():
    rq = EndpointDB('127.0.0.1')
    rq.connect()
    ep_id = str(uuid.uuid4())
    for i in range(20):
        rq.put(ep_id, {'c': i, 'm': i*100})

    res = rq.get(ep_id, timeout=1)
    print("Result : ", res)


if __name__ == '__main__':
    test()
