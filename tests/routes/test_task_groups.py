from funcx_web_service.models.tasks import TaskGroup
from tests.routes.app_test_base import AppTestBase


class TestTaskGroups(AppTestBase):
    def test_get_batch_info(self, mocker, mock_user, mock_auth_client, mock_redis):
        TaskGroup(mock_redis, "123", user_id=mock_user.id)
        exists_spy = mocker.spy(TaskGroup, "exists")

        result = self.client.get(
            "/api/v1/task_groups/123", headers={"Authorization": "my_token"}
        )
        assert result.json["authorized"]
        exists_spy.assert_called_with(mock_redis, "123")
