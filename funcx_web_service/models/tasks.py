import typing as t
from datetime import datetime, timedelta
from enum import Enum

from funcx_common.redis import (
    INT_SERDE,
    JSON_SERDE,
    FuncxRedisEnumSerde,
    HasRedisFieldsMeta,
    RedisField,
)
from funcx_common.tasks import TaskProtocol, TaskState
from redis import Redis
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from funcx_web_service.models import db


# This internal state is never shown to the user and is meant to track whether
# or not the forwarder has succeeded in fully processing the task
class InternalTaskState(str, Enum):
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"


class DBTask(db.Model):
    __tablename__ = "tasks"
    id = db.Column(Integer, primary_key=True)
    user_id = db.Column(Integer, ForeignKey("users.id"))
    task_uuid = db.Column(String(38))
    status = db.Column(String(10), default="UNKNOWN")
    created_at = db.Column(DateTime, default=datetime.utcnow)
    modified_at = db.Column(DateTime, default=datetime.utcnow)
    endpoint_id = db.Column(String(38), ForeignKey("sites.endpoint_uuid"))
    function_id = db.Column(String(38), ForeignKey("functions.function_uuid"))

    function = relationship("Function", back_populates="tasks")
    endpoint = relationship("Endpoint", back_populates="tasks")

    user = relationship("User", back_populates="tasks")

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()


class RedisTask(TaskProtocol, metaclass=HasRedisFieldsMeta):
    """
    ORM-esque class to wrap access to properties of tasks for better style and
    encapsulation
    """

    status = t.cast(TaskState, RedisField(serde=FuncxRedisEnumSerde(TaskState)))
    internal_status = t.cast(
        InternalTaskState, RedisField(serde=FuncxRedisEnumSerde(InternalTaskState))
    )
    user_id = RedisField(serde=INT_SERDE)
    function_id = RedisField()
    endpoint = t.cast(str, RedisField())
    container = RedisField()
    data_url = RedisField()
    recursive = RedisField()
    payload = RedisField(serde=JSON_SERDE)
    result = RedisField()
    result_reference = t.cast(
        t.Optional[t.Dict[str, t.Any]], RedisField(serde=JSON_SERDE)
    )
    exception = RedisField()
    completion_time = RedisField()
    task_group_id = RedisField()

    # must keep ttl and _set_expire in merge
    # tasks expire in 1 week, we are giving some grace period for
    # long-lived clients, and we'll revise this if there are complaints
    TASK_TTL = timedelta(weeks=2)

    def __init__(
        self,
        redis_client: Redis,
        task_id: str,
        *,
        user_id: t.Optional[int] = None,
        function_id: t.Optional[str] = None,
        container: t.Optional[str] = None,
        payload: t.Any = None,
        data_url: str = "",
        recursive: str = "",
        task_group_id: t.Optional[str] = None,
    ):
        """
        If optional values are passed, then they will be written.
        Otherwise, they will fetched from any existing task entry.

        :param redis_client: Redis client for properties to get/set
        :param task_id: UUID of the task, as str
        :param user_id: ID of user to whom this task belongs
        :param function_id: UUID of the function for this task, as str
        :param container: UUID of container in which to run, as str
        :param payload: serialized function + input data
        :param task_group_id: UUID of task group that this task belongs to
        """
        self.redis_client = redis_client
        self.task_id = task_id
        self.hname = f"task_{task_id}"

        # if required attributes are not yet set, initialize them to their defaults
        if self.status is None:
            self.status = TaskState.WAITING_FOR_EP
        if self.internal_status is None:
            self.internal_status = InternalTaskState.INCOMPLETE

        if user_id is not None:
            self.user_id = user_id
        if function_id is not None:
            self.function_id = function_id
        if container is not None:
            self.container = container
        if payload is not None:
            self.payload = payload
        if task_group_id is not None:
            self.task_group_id = task_group_id

        self.data_url = data_url
        self.recursive = recursive
        # check the header effect
        # Used to pass bits of information to EP
        self.header = (
            f"{self.task_id};{self.container};" f"{self.data_url};{self.recursive}"
        )
        self._set_expire()

    def _set_expire(self):
        """Expires task after TASK_TTL, if not already set."""
        ttl = self.redis_client.ttl(self.hname)
        if ttl < 0:
            # expire was not already set
            self.redis_client.expire(self.hname, RedisTask.TASK_TTL)

    def delete(self):
        """Removes this task from Redis, to be used after the result is gotten"""
        self.redis_client.delete(self.hname)

    @classmethod
    def exists(cls, redis_client: Redis, task_id: str) -> bool:
        """Check if a given task_id exists in Redis"""
        return bool(redis_client.exists(f"task_{task_id}"))


class TaskGroup(metaclass=HasRedisFieldsMeta):
    """
    ORM-esque class to wrap access to properties of batches for better style and
    encapsulation
    """

    user_id = RedisField(serde=INT_SERDE)

    TASK_GROUP_TTL = timedelta(weeks=1)

    def __init__(self, redis_client: Redis, task_group_id: str, user_id: int = None):
        """
        If the kwargs are passed, then they will be overwritten.  Otherwise, they
        will gotten from existing task entry.

        :param redis_client: Redis client so that properties can get/set
        """
        self.redis_client = redis_client
        self.task_group_id = task_group_id
        self.hname = f"task_group_{task_group_id}"

        if user_id is not None:
            self.user_id = user_id

        self.header = self.task_group_id
        self._set_expire()

    def _set_expire(self):
        """Expires task after TASK_TTL, if not already set."""
        ttl = self.redis_client.ttl(self.hname)
        if ttl < 0:
            # expire was not already set
            self.redis_client.expire(self.hname, TaskGroup.TASK_GROUP_TTL)

    def delete(self):
        """Removes this task group from Redis, to be used after the result is gotten"""
        self.redis_client.delete(self.hname)

    @classmethod
    def exists(cls, redis_client: Redis, task_group_id: str) -> bool:
        """Check if a given task_group_id exists in Redis"""
        return bool(redis_client.exists(f"task_group_{task_group_id}"))
