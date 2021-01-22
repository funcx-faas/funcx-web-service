from types import SimpleNamespace
import pytest
from funcx_web_service.models.container import Container
from funcx_web_service.models.function import Function
from funcx_web_service.models.user import User
from tests.routes.app_test_base import AppTestBase


@pytest.fixture
def mock_user(mocker):
    return User(
        username='bob',
        globus_identity='123-456'
    )


@pytest.fixture
def mock_auth_client(mocker, mock_user):
    import funcx_web_service.authentication
    mock_auth_client = mocker.Mock()
    mock_auth_client.oauth2_token_introspect = mocker.Mock(
        return_value={
            "username": "bob",
            "sub": "123-456",
            "active": True,
            "scope": "https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all",
        })

    mocker.patch.object(funcx_web_service.authentication.auth, "get_auth_client",
                        return_value=mock_auth_client)

    mocker.patch('funcx_web_service.authentication.auth.User.resolve_user', return_value=mock_user)

    return mock_auth_client


@pytest.fixture
def mock_redis(mocker):
    import funcx_web_service.models

    mock_redis = mocker.Mock()
    mocker.patch.object(funcx_web_service.models.utils,
                        "get_redis_client",
                        return_value=mock_redis)
    return mock_redis


class TestFuncX(AppTestBase):
    def test_get_status(self, mock_auth_client, mock_redis, mocker):

        from funcx_web_service.models.tasks import Task
        mock_task = SimpleNamespace(status="ready")
        mock_exists = mocker.patch.object(Task, "exists", return_value=True)
        mock_from_id = mocker.patch.object(Task, "from_id", return_value=mock_task)

        client = self.test_client()

        result = client.get("/api/v1/tasks/42/status", headers={"Authorization": "my_token"})

        # Need to get mock get_redis_client working
        mock_exists.assert_called_with(None, "42")
        mock_from_id.assert_called_with(None, "42")
        assert result.json['status'] == 'ready'

    def test_register_function(self, mock_auth_client, mocker):
        mock_ingest = mocker.patch("funcx_web_service.routes.funcx.ingest_function")
        client = self.test_client()
        result = client.post("api/v1/register_function",
                             json={
                                 "function_source": "def fun(x): return x+1",
                                 "function_name": "test fun",
                                 "entry_point": "func()",
                                 "description": "this is a test",
                                 "function_code": "flksdjfldkjdlkfjslk",
                                 "public": True
                             },
                             headers={"Authorization": "my_token"})
        assert result.status_code == 200
        assert "function_uuid" in result.json

        with client.application.app_context():
            saved_function = Function.find_by_uuid(result.json['function_uuid'])
            assert saved_function.function_uuid == result.json['function_uuid']
            assert saved_function.function_name == 'test fun'
            assert saved_function.entry_point == "func()"
            assert saved_function.description == 'this is a test'
            assert saved_function.function_source_code == "flksdjfldkjdlkfjslk"
            assert saved_function.public

            assert mock_ingest.call_args[0][0].function_uuid == result.json['function_uuid']
            assert mock_ingest.call_args[0][1] == 'def fun(x): return x+1'
            assert mock_ingest.call_args[0][2] == '123-456'

    def test_register_function_no_search(self, mock_auth_client, mocker):
        mock_ingest = mocker.patch("funcx_web_service.routes.funcx.ingest_function")
        client = self.test_client()
        from funcx_web_service.models.user import User
        mock_user = User(
            id=42,
            username="bob"
        )

        mocker.patch.object(User, "find_by_username", return_value=mock_user)
        result = client.post("api/v1/register_function",
                             json={
                                 "function_source": "def fun(x): return x+1",
                                 "function_name": "test fun",
                                 "entry_point": "func()",
                                 "description": "this is a test",
                                 "function_code": "flksdjfldkjdlkfjslk",
                                 "public": True,
                                 "searchable": False
                             },
                             headers={"Authorization": "my_token"})
        assert result.status_code == 200
        assert "function_uuid" in result.json
        assert mock_ingest.not_called

    def test_register_function_with_container(self, mock_auth_client, mocker):
        mock_ingest = mocker.patch("funcx_web_service.routes.funcx.ingest_function")
        client = self.test_client()
        from funcx_web_service.models.user import User
        mock_user = User(
            id=42,
            username="bob"
        )
        mocker.patch.object(User, "find_by_username", return_value=mock_user)

        from funcx_web_service.models.container import Container
        mock_container = Container(
            id=44
        )

        mock_container_read = mocker.patch.object(Container, "find_by_uuid", return_value=mock_container)
        result = client.post("api/v1/register_function",
                             json={
                                 "function_source": "def fun(x): return x+1",
                                 "function_name": "test fun",
                                 "entry_point": "func()",
                                 "description": "this is a test",
                                 "function_code": "flksdjfldkjdlkfjslk",
                                 "public": True,
                                 "searchable": False,
                                 "container_uuid": '11122-22111'
                             },
                             headers={"Authorization": "my_token"})
        assert result.status_code == 200
        assert "function_uuid" in result.json
        assert mock_ingest.not_called
        mock_container_read.assert_called_with("11122-22111")
        with client.application.app_context():
            saved_function = Function.find_by_uuid(result.json['function_uuid'])
            assert saved_function.container.container_id == 44

    def test_register_function_with_group_auth(self, mock_auth_client, mocker):
        mock_ingest = mocker.patch("funcx_web_service.routes.funcx.ingest_function")
        client = self.test_client()
        from funcx_web_service.models.user import User
        mock_user = User(
            id=42,
            username="bob"
        )
        mocker.patch.object(User, "find_by_username", return_value=mock_user)

        from funcx_web_service.models.auth_groups import AuthGroup
        mock_auth_group = AuthGroup(
            id=45
        )

        mock_authgroup_read = mocker.patch.object(AuthGroup, "find_by_uuid", return_value=mock_auth_group)
        result = client.post("api/v1/register_function",
                             json={
                                 "function_source": "def fun(x): return x+1",
                                 "function_name": "test fun",
                                 "entry_point": "func()",
                                 "description": "this is a test",
                                 "function_code": "flksdjfldkjdlkfjslk",
                                 "public": True,
                                 "searchable": False,
                                 "group": '222-111'
                             },
                             headers={"Authorization": "my_token"})
        assert result.status_code == 200
        assert "function_uuid" in result.json
        assert mock_ingest.not_called
        mock_authgroup_read.assert_called_with("222-111")
        with client.application.app_context():
            saved_function = Function.find_by_uuid(result.json['function_uuid'])
            assert len(saved_function.auth_groups) == 1
            assert saved_function.auth_groups[0].group_id == 45

    def test_register_container(self, mocker, mock_auth_client):
        client = self.test_client()
        result = client.post("api/v1/containers",
                             json={
                                 "name": "myContainer",
                                 "function_name": "test fun",
                                 "description": "this is a test",
                                 "type": "docker",
                                 "location": "http://hub.docker.com/myContainer",
                             },
                             headers={"Authorization": "my_token"})
        assert result.status_code == 200
        assert "container_id" in result.json
        container_uuid = result.json['container_id']
        with client.application.app_context():
            saved_container = Container.find_by_uuid(container_uuid)
            assert saved_container
            assert saved_container.name == 'myContainer'
            assert saved_container.container_uuid == container_uuid
            assert saved_container.description == 'this is a test'

            assert saved_container.images
            assert len(saved_container.images) == 1
            assert saved_container.images[0].type == 'docker'
            assert saved_container.images[0].location == 'http://hub.docker.com/myContainer'

    def test_register_container_invalid_spec(self, mocker, mock_auth_client):
        client = self.test_client()
        result = client.post("api/v1/containers",
                             json={
                                 "type": "docker",
                                 "location": "http://hub.docker.com/myContainer",
                             },
                             headers={"Authorization": "my_token"})
        assert result.status_code == 400

    def test_register_endpoint(self, mocker, mock_auth_client, mock_user):
        client = self.test_client()

        get_forwarder_version = mocker.patch(
            "funcx_web_service.routes.funcx.get_forwarder_version",
            return_value={"min_ep_version": "1.0.0"})

        mock_register_endpoint = \
            mocker.patch("funcx_web_service.routes.funcx.register_endpoint",
                         return_value="123-45-6789-1011")

        mock_register_with_hub = \
            mocker.patch("funcx_web_service.routes.funcx.register_with_hub",
                         return_value="Ok")

        result = client.post("api/v1/register_endpoint_2",
                             json={
                                 "version": "1.0.0",
                                 "endpoint_name": "my-endpoint",
                                 "endpoint_uuid": None
                             },
                             headers={"Authorization": "my_token"})
        get_forwarder_version.assert_called()
        mock_register_endpoint.assert_called_with(
            mock_user, 'my-endpoint', '', endpoint_uuid=None)

        mock_register_with_hub.assert_called_with('http://192.162.3.5:8080',
                                                  '123-45-6789-1011',
                                                  '127.0.0.1')

        assert result.status_code == 200

    def test_register_endpoint_version_mismatch(self, mocker, mock_auth_client):
        client = self.test_client()
        get_forwarder_version = mocker.patch(
            "funcx_web_service.routes.funcx.get_forwarder_version",
            return_value={"min_ep_version": "1.42.0"})

        result = client.post("api/v1/register_endpoint_2",
                             json={
                                 "version": "1.0.0"
                             },
                             headers={"Authorization": "my_token"})
        get_forwarder_version.assert_called()
        assert result.status_code == 400
        assert "Endpoint is out of date." in result.data.decode("utf-8")

    def test_register_endpoint_no_version(self, mocker, mock_auth_client):
        client = self.test_client()
        get_forwarder_version = mocker.patch(
            "funcx_web_service.routes.funcx.get_forwarder_version",
            return_value={"min_ep_version": "1.42.0"})

        result = client.post("api/v1/register_endpoint_2",
                             json={
                             },
                             headers={"Authorization": "my_token"})
        get_forwarder_version.assert_called()
        assert result.status_code == 400
        assert "version must be passed in" in result.data.decode("utf-8")
