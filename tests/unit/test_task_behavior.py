import uuid

from funcx_common.tasks import TaskState

from funcx_web_service.models.tasks import InternalTaskState, RedisTask, TaskGroup


def test_redis_task_creation(mock_redis):
    task_id = str(uuid.uuid1())

    assert not RedisTask.exists(mock_redis, task_id)
    new_task = RedisTask(mock_redis, task_id)

    assert RedisTask.exists(mock_redis, task_id)
    assert new_task.status == TaskState.WAITING_FOR_EP
    assert new_task.internal_status == InternalTaskState.INCOMPLETE


# this is a regression test for a bug in which newly created RedisTask objects would
# "reset" the status and internal_status fields of a task
def test_redis_task_double_lookup(mock_redis):
    task_id = str(uuid.uuid1())

    assert not RedisTask.exists(mock_redis, task_id)
    new_task = RedisTask(mock_redis, task_id)
    new_task.status = TaskState.SUCCESS
    new_task.internal_status = InternalTaskState.COMPLETE

    assert RedisTask.exists(mock_redis, task_id)
    second_task = RedisTask(mock_redis, task_id)
    assert second_task.status == TaskState.SUCCESS
    assert second_task.internal_status == InternalTaskState.COMPLETE


def test_redis_task_delete(mock_redis):
    task_id = str(uuid.uuid1())

    assert not RedisTask.exists(mock_redis, task_id)
    task = RedisTask(mock_redis, task_id)

    assert RedisTask.exists(mock_redis, task_id)
    task.delete()

    assert not RedisTask.exists(mock_redis, task_id)


def test_task_group_create(mock_redis):
    task_group_id = str(uuid.uuid1())
    user_id = 101

    assert not TaskGroup.exists(mock_redis, task_group_id)

    tg = TaskGroup(mock_redis, task_group_id, user_id=user_id)
    assert tg.user_id == user_id

    assert TaskGroup.exists(mock_redis, task_group_id)


def test_task_group_delete(mock_redis):
    task_group_id = str(uuid.uuid1())
    user_id = 101

    assert not TaskGroup.exists(mock_redis, task_group_id)
    tg = TaskGroup(mock_redis, task_group_id, user_id=user_id)
    assert TaskGroup.exists(mock_redis, task_group_id)
    tg.delete()
    assert not TaskGroup.exists(mock_redis, task_group_id)


def test_task_group_no_user_id(mock_redis):
    # creating a TaskGroup without setting user_id results in no creation within redis,
    # and the TaskGroup does not exist
    # TODO: determine if this is the desired behavior
    # maybe __init__ should raise an exception if `user_id` is not set?
    task_group_id = str(uuid.uuid1())

    assert not TaskGroup.exists(mock_redis, task_group_id)

    tg = TaskGroup(mock_redis, task_group_id)
    assert tg.user_id is None

    assert not TaskGroup.exists(mock_redis, task_group_id)
