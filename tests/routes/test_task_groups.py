from funcx_web_service.models.tasks import TaskGroup
from tests.routes.app_test_base import AppTestBase


class TestTaskGroups(AppTestBase):
    def test_get_batch_info(self, mocker, mock_user, mock_auth_client, mock_redis):
        mock_redis.hset("task_group_123", "user_id", 22)
        mock_redis.expire("task_group_123", 10)

        task_group = TaskGroup(mock_redis, "123")
        mock_from_id = mocker.patch.object(
            TaskGroup, "from_id", return_value=task_group
        )
        exists_spy = mocker.spy(TaskGroup, "exists")

        result = self.client.get(
            "/api/v1/task_groups/123", headers={"Authorization": "my_token"}
        )
        assert result.json["authorized"]
        mock_from_id.assert_called_with(mock_redis, "123")
        exists_spy.assert_called_with(mock_redis, "123")
