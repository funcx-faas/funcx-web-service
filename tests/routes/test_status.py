from funcx_web_service.models.user import User
from unittest.mock import call
from unittest.mock import Mock

from funcx_web_service.models.tasks import Task
from tests.routes.app_test_base import AppTestBase


class TestStatus(AppTestBase):
    def test_get_status(self, mock_auth_client, mock_redis, mock_user: User, mocker):
        get_rc = mocker.patch(
            "funcx_web_service.routes.funcx.g_redis_client",
            return_value=mock_redis)
        rf_get = mocker.patch(
            "funcx_web_service.models.tasks.RedisField.__get__",
            return_value=True)

        mocker.patch.object(Task, "user_id").__get__ = Mock(return_value=mock_user.id)
        mock_expire = mocker.patch.object(Task, "_set_expire", return_value=123)
        mock_exists = mocker.patch.object(Task, "exists", return_value=True)

        task_id = "42"
        task = Task(mock_redis(), task_id=task_id)
        mock_from_id = mocker.patch.object(Task, "from_id", return_value=task)

        result = self.client.get(f"/api/v1/tasks/{task_id}", headers={"Authorization": "my_token"})

        mock_exists.assert_called()
        mock_expire.assert_called()
        mock_from_id.assert_called()
        rf_get.assert_called()
        get_rc.assert_called()
        assert result.status_code == 200
        assert result.json["task_id"] == "42", result.json

    def test_unauthorized_get_status(self, mock_auth_client, mock_redis, mock_user: User, mocker):
        """
        Verify that a user cannot retrieve a Task status which is not theirs
        """
        get_rc = mocker.patch(
            "funcx_web_service.routes.funcx.g_redis_client",
            return_value=mock_redis)

        mocker.patch.object(Task, "user_id").__get__ = Mock(return_value=123)
        mock_expire = mocker.patch.object(Task, "_set_expire", return_value=123)
        mock_exists = mocker.patch.object(Task, "exists", return_value=True)

        task_id = "42"
        task = Task(mock_redis(), task_id=task_id)
        mock_from_id = mocker.patch.object(Task, "from_id", return_value=task)

        result = self.client.get(f"/api/v1/tasks/{task_id}", headers={"Authorization": "my_token"})

        mock_exists.assert_called()
        mock_expire.assert_called()
        mock_from_id.assert_called()
        get_rc.assert_called()

        assert result.status_code == 404
        assert result.json["status"] == "Failed", result.json

    def test_get_batch_status(self, mocker, mock_auth_client, mock_redis, mock_user: User):
        mock_exists = mocker.patch.object(Task, "exists", return_value=True)
        mocker.patch.object(Task, "_set_expire", return_value=123)
        mocker.patch.object(Task, "user_id").__get__ = Mock(return_value=mock_user.id)

        mocker.patch(
            "funcx_web_service.models.tasks.RedisField.__get__",
            return_value=True)

        tasks = [Task(mock_redis, "1"), Task(mock_redis, "1")]
        mock_from_id = mocker.patch.object(Task, "from_id", side_effect=tasks)

        client = self.client
        result = client.post("/api/v1/batch_status",
                             headers={"Authorization": "my_token"},
                             json={
                                 "task_ids": ["1", "2"]
                             })
        assert result
        results = result.json['results']
        assert '1' in results
        assert '2' in results
        for task_id in result.json["results"]:
            fields_in_results = all(k in result.json["results"][task_id] for k in (
                'completion_t', 'exception', 'result', 'status')
            )
            assert fields_in_results

        mock_exists.assert_has_calls([call(mock_redis, "1"), call(mock_redis, "2")])
        mock_from_id.assert_has_calls([call(mock_redis, "1"), call(mock_redis, "2")])

    def test_unauthorized_get_batch_status(self, mocker, mock_auth_client, mock_redis):
        """
        Verify that a user cannot retrieve a status for a Batch which is not theirs
        """
        mocker.patch(
            "funcx_web_service.models.tasks.RedisField.__get__",
            return_value=True)
        mock_exists = mocker.patch.object(Task, "exists", return_value=True)
        mocker.patch.object(Task, "_set_expire", return_value=123)
        mocker.patch.object(Task, "user_id").__get__ = Mock(return_value=123)

        tasks = [Task(mock_redis, "1"), Task(mock_redis, "1")]
        mock_from_id = mocker.patch.object(Task, "from_id", side_effect=tasks)

        client = self.client
        result = client.post("/api/v1/batch_status",
                             headers={"Authorization": "my_token"},
                             json={
                                 "task_ids": ["1", "2"]
                             })

        assert result.status_code == 200
        assert "results" in result.json, result.json
        assert '1' in result.json['results']
        assert '2' in result.json['results']
        for task_id in result.json["results"]:
            assert result.json["results"][task_id]["reason"] == "Unknown task id"
            assert result.json["results"][task_id]["status"] == "Failed"

        mock_exists.assert_has_calls([call(mock_redis, "1"), call(mock_redis, "2")])
        mock_from_id.assert_has_calls([call(mock_redis, "1"), call(mock_redis, "2")])
