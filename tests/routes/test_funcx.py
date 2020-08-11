from types import SimpleNamespace
import pytest
from funcx_web_service.application import create_app


@pytest.fixture
def mock_auth_client(mocker):
    import funcx_web_service.authentication
    mock_auth_client = mocker.Mock()
    mock_auth_client.oauth2_token_introspect = mocker.Mock(
        return_value={"username": "bob"})

    mocker.patch.object(funcx_web_service.authentication.auth, "get_auth_client",
                        return_value=mock_auth_client)

    return mock_auth_client


@pytest.fixture
def mock_redis(mocker):
    import funcx_web_service.models

    mock_redis = mocker.Mock()
    mocker.patch.object(funcx_web_service.models.utils,
                        "get_redis_client",
                        return_value=mock_redis)
    return mock_redis


class TestFuncX:
    def test_get_status(self, mock_auth_client, mock_redis, mocker):

        from funcx_web_service.models.tasks import Task
        mock_task = SimpleNamespace(status="ready")
        mock_exists = mocker.patch.object(Task, "exists", return_value=True)
        mock_from_id = mocker.patch.object(Task, "from_id", return_value=mock_task)

        client = create_app({}).test_client()

        result = client.get("/api/v1/tasks/42/status", headers={"Authorization": "my_token"})

        # Need to get mock get_redis_client working
        mock_exists.assert_called_with(None, "42")
        mock_from_id.assert_called_with(None, "42")
        assert result.json['status'] == 'ready'
