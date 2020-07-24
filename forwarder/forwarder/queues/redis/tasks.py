import json
from datetime import timedelta
from enum import Enum

from redis import StrictRedis

from funcx.executors.high_throughput.messages import TaskStatusCode


# We subclass from str so that the enum can be JSON-encoded without adjustment
class TaskState(str, Enum):
    RECEIVED = "received"  # on receiving a task web-side
    WAITING_FOR_EP = "waiting-for-ep"  # while waiting for ep to accept/be online
    WAITING_FOR_NODES = "waiting-for-nodes"  # jobs are pending at the scheduler
    WAITING_FOR_LAUNCH = "waiting-for-launch"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


def status_code_convert(code):
    return {
        TaskStatusCode.WAITING_FOR_NODES: TaskState.WAITING_FOR_NODES,
        TaskStatusCode.WAITING_FOR_LAUNCH: TaskState.WAITING_FOR_LAUNCH,
        TaskStatusCode.RUNNING: TaskState.RUNNING,
        TaskStatusCode.SUCCESS: TaskState.SUCCESS,
        TaskStatusCode.FAILED: TaskState.FAILED
    }[code]


class RedisField:
    """
    Descriptor class that stores data in redis.

    Uses owning class's redis client in `owner.rc` to connect, and uses owner's hname in `owner.hname` to uniquely
    identify the keys.

    Serializer and deserializer parameters are callables that are executed on get and set so that things like
    dicts can be stored in redis.
    """
    # TODO: have a cache and TTL on the properties so that we aren't making so many redis gets?
    def __init__(self, serializer=None, deserializer=None):
        self.key = ""
        self.serializer = serializer
        self.deserializer = deserializer

    def __get__(self, owner, ownertype):
        val = owner.rc.hget(owner.hname, self.key)
        if self.deserializer:
            val = self.deserializer(val)
        return val

    def __set__(self, owner, val):
        if self.serializer:
            val = self.serializer(val)
        owner.rc.hset(owner.hname, self.key, val)


def auto_name_fields(klass):
    """Class decorator to auto name RedisFields
    Inspects class attributes, and tells RedisFields what their keys are based on attribute name.

    This isn't necessary, but avoids duplication.  Otherwise we'd have to say e.g.
        status = RedisField("status")
    """
    for name, attr in klass.__dict__.items():
        if isinstance(attr, RedisField):
            attr.key = name
    return klass


@auto_name_fields
class Task:
    """
    ORM-esque class to wrap access to properties of tasks for better style and encapsulation
    """
    status = RedisField(serializer=lambda ts: ts.value, deserializer=TaskState)
    endpoint = RedisField()
    container = RedisField()
    payload = RedisField(serializer=json.dumps, deserializer=json.loads)
    result = RedisField()
    exception = RedisField()
    completion_time = RedisField()

    # must keep ttl and _set_expire in merge
    TASK_TTL = timedelta(weeks=1)
    
    def __init__(self, rc: StrictRedis, task_id: str, container: str = "", serializer: str = "", payload: str = ""):
        """ If the kwargs are passed, then they will be overwritten.  Otherwise, they will gotten from existing
        task entry.
        Parameters
        ----------
        rc : StrictRedis
            Redis client so that properties can get get/set
        task_id : str
            UUID of task
        container : str
            UUID of container in which to run
        serializer : str
        payload : str
            serialized function + input data
        """
        self.rc = rc
        self.task_id = task_id
        self.hname = self._generate_hname(self.task_id)

        # If passed, we assume they should be set (i.e. in cases of new tasks)
        # if not passed,
        if container:
            self.container = container

        # Serializer is weird: it's basically deprecated, but keep it around for old-time's sake
        # Don't store in redis, so we need to provide default value.
        if serializer:
            self.serializer = serializer
        else:
            self.serializer = "None"

        if payload:
            self.payload = payload

        self.header = self._generate_header()

        self._set_expire()

    @staticmethod
    def _generate_hname(task_id):
        return f'task_{task_id}'

    def _set_expire(self):
        """Expires task after TASK_TTL, if not already set."""
        ttl = self.rc.ttl(self.hname)
        if ttl < 0:
            # expire was not already set
            self.rc.expire(self.hname, Task.TASK_TTL)
            
    def _generate_header(self):
        """Used to pass bits of information to EP"""
        return f'{self.task_id};{self.container};{self.serializer}'

    @classmethod
    def exists(cls, rc: StrictRedis, task_id: str):
        """Check if a given task_id exists in Redis"""
        task_hname = cls._generate_hname(task_id)
        return rc.exists(task_hname)

    @classmethod
    def from_id(cls, rc: StrictRedis, task_id: str):
        """For more readable code, use this to find a task by id, using the redis client"""
        return cls(rc, task_id)

    def delete(self):
        """Removes this task from Redis, to be used after the result is gotten"""
        self.rc.delete(self.hname)
