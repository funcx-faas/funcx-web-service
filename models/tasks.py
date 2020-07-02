import json
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


class Task:
    """
    ORM-esque class to wrap access to properties of tasks for better style and encapsulation

    TODO: have a cache and TTL on the properties so that we aren't making so many redis gets?
    """
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
        self._task_hname = self._generate_hname(self.task_id)

        # If passed, we assume they should be set (i.e. in cases of new tasks)
        # if not passed,
        if container:
            self.container = container

        if serializer:
            self.serializer = serializer

        if payload:
            self.payload = payload

        self.header = self._generate_header()

    @staticmethod
    def _generate_hname(task_id):
        return f'task_{task_id}'

    def _generate_header(self):
        """Used to pass bits of information to EP"""
        return f'{self.task_id};{self.container};{self.serializer}'

    def _get(self, key):
        """Get's the value of key via redis"""
        return self.rc.hget(self._task_hname, key)

    def _set(self, key, value):
        """Sets key -> value in Redis"""
        self.rc.hset(self._task_hname, key, value)

    @property
    def status(self) -> TaskState:
        """Get or set status in Redis"""
        return TaskState(self._get('status'))

    @status.setter
    def status(self, s: TaskState):
        self._set('status', s.value)

    @property
    def endpoint(self):
        """Get or set endpoint id in Redis"""
        return self._get('endpoint')

    @endpoint.setter
    def endpoint(self, ep):
        self._set('endpoint', ep)

    @property
    def container(self):
        """Get or set container id in Redis"""
        return self._get('container')

    @container.setter
    def container(self, c):
        self._set('container', c)

    @property
    def payload(self):
        """Get or set payload object in Redis (automatically json.loads or json.dumps)"""
        return json.loads(self._get('payload'))

    @payload.setter
    def payload(self, p):
        self._set('payload', json.dumps(p))

    @property
    def result(self):
        """Get or set result object in Redis (automatically json.loads or json.dumps)"""
        r = self._get('result')
        if r:
            r = json.loads(r)
        return r

    @result.setter
    def result(self, r):
        self._set('result', json.dumps(r))

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
        self.rc.delete(self._task_hname)
