import json
from datetime import timedelta
from enum import Enum

from redis import StrictRedis


# We subclass from str so that the enum can be JSON-encoded without adjustment
class TaskState(str, Enum):
    RECEIVED = "received"  # on receiving a task web-side
    WAITING_FOR_EP = "waiting-for-ep"  # while waiting for ep to accept/be online
    WAITING_FOR_NODES = "waiting-for-nodes"  # jobs are pending at the scheduler
    WAITING_FOR_LAUNCH = "waiting-for-launch"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


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
    user_id = RedisField(serializer=str, deserializer=int)
    function_id = RedisField()
    endpoint = RedisField()
    container = RedisField()
    payload = RedisField(serializer=json.dumps, deserializer=json.loads)
    result = RedisField()
    exception = RedisField()
    completion_time = RedisField()
    task_group_id = RedisField()

    # must keep ttl and _set_expire in merge
    # tasks expire in 1 week, we are giving some grace period for
    # long-lived clients, and we'll revise this if there are complaints
    TASK_TTL = timedelta(weeks=2)

    def __init__(
        self,
        rc: StrictRedis,
        task_id: str,
        user_id: int = -1,
        function_id: str = "",
        container: str = "",
        serializer: str = "",
        payload: str = "",
        task_group_id: str = "",
    ):
        """If the kwargs are passed, then they will be overwritten.  Otherwise, they will gotten from existing
        task entry.
        Parameters
        ----------
        rc : StrictRedis
            Redis client so that properties can get get/set
        task_id : str
            UUID of task
        user_id : int
            ID of user that this task belongs to
        function_id : str
            UUID of function for task
        container : str
            UUID of container in which to run
        serializer : str
        payload : str
            serialized function + input data
        task_group_id : str
            UUID of task group that this task belongs to
        """
        self.rc = rc
        self.task_id = task_id
        self.hname = self._generate_hname(self.task_id)

        # If passed, we assume they should be set (i.e. in cases of new tasks)
        # if not passed, do not set
        if user_id != -1:
            self.user_id = user_id

        if function_id:
            self.function_id = function_id

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

        if task_group_id:
            self.task_group_id = task_group_id

        self.header = self._generate_header()
        self._set_expire()

    @staticmethod
    def _generate_hname(task_id):
        return f"task_{task_id}"

    def _set_expire(self):
        """Expires task after TASK_TTL, if not already set."""
        ttl = self.rc.ttl(self.hname)
        if ttl < 0:
            # expire was not already set
            self.rc.expire(self.hname, Task.TASK_TTL)

    def _generate_header(self):
        """Used to pass bits of information to EP"""
        return f"{self.task_id};{self.container};{self.serializer}"

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
