from enum import Enum

from redis import StrictRedis


class TaskState(Enum):
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
    """
    def __init__(self, rc: StrictRedis, task_id: str, container: str, serializer: str, payload: str):
        """

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
        self._task_hname = f'task_{self.task_id}'
        self.container = container
        self.serializer = serializer
        self.payload = payload

        self._task_header = self._generate_header()

    def _generate_header(self):
        """Used to pass bits of information to EP"""
        return f'{self.task_id};{self.container};{self.serializer}'

    @property
    def status(self) -> TaskState:
        return TaskState(self.rc.hget(self._task_hname, 'status'))

    @status.setter
    def status(self, s: TaskState):
        self.rc.hset(self._task_hname, 'status', s.value)