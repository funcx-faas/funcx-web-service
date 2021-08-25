from funcx_web_service.models.tasks import TaskGroup
from tests.routes.app_test_base import AppTestBase


class TestTaskGroups(AppTestBase):
    def test_get_batch_info(self, mocker, mock_user, mock_auth_client, mock_redis):
        mocker.patch(
            "funcx_web_service.models.tasks.RedisField.__get__",
            return_value=22)

        mock_redis.ttl = mocker.Mock(return_value=10)
        task_group = TaskGroup(mock_redis, "123", 22)
        mock_from_id = mocker.patch.object(TaskGroup, "from_id", return_value=task_group)
        mock_exists = mocker.patch.object(TaskGroup, "exists", return_value=True)

        result = self.client.get("/api/v1/task_groups/123", headers={"Authorization": "my_token"})
        assert result.json['authorized']
        mock_from_id.assert_called_with(mock_redis, "123")
        mock_exists.assert_called_with(mock_redis, "123")
