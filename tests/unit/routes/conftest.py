import pytest
from funcx_common.tasks import TaskState

from funcx_web_service.models.endpoint import Endpoint
from funcx_web_service.models.tasks import InternalTaskState, RedisTask
from funcx_web_service.models.user import User


@pytest.fixture
def mock_user():
    return User(username="bob", globus_identity="123-456", id=22)


@pytest.fixture
def mock_endpoint():
    return Endpoint(
        user_id=1,
        endpoint_uuid="11111111-2222-3333-4444-555555555555",
        restricted=True,
        restricted_functions=[],
    )


@pytest.fixture
def mock_redis_task_factory(mock_redis, mock_user, mocker):
    def func(task_id, user_id=mock_user.id, status=None, internal_status=None):
        t = RedisTask(mock_redis, task_id=task_id)
        t.user_id = user_id
        t.status = TaskState.WAITING_FOR_EP
        t.internal_status = InternalTaskState.INCOMPLETE
        return t

    return func
