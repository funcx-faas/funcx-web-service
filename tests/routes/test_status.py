from funcx_web_service.models.tasks import Task
from tests.routes.app_test_base import AppTestBase


class TestStatus(AppTestBase):
    def test_get_status(self, mock_auth_client, mock_redis, mocker):

        get_rc = mocker.patch(
            "funcx_web_service.routes.funcx.g_redis_client",
            return_value=mock_redis)

        rf_get = mocker.patch(
            "funcx_web_service.models.tasks.RedisField.__get__",
            return_value=True)

        mock_expire = mocker.patch.object(Task, "_set_expire", return_value=123)
        mock_exists = mocker.patch.object(Task, "exists", return_value=True)

        task = Task(mock_redis(), "42")
        mock_from_id = mocker.patch.object(Task, "from_id", return_value=task)

        client = self.client

        result = client.get("/api/v1/tasks/42", headers={"Authorization": "my_token"})

        mock_exists.assert_called()
        mock_expire.assert_called()
        mock_from_id.assert_called()
        rf_get.assert_called()
        get_rc.assert_called()

        assert result.json["task_id"] == "42"
