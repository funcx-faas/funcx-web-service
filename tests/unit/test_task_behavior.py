import uuid

from funcx_common.tasks import TaskState

from funcx_web_service.models.tasks import InternalTaskState, RedisTask


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
