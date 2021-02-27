from types import SimpleNamespace
import pytest
from funcx_web_service.models.container import Container
from funcx_web_service.models.endpoint import Endpoint
from funcx_web_service.models.function import Function
from funcx_web_service.models.user import User
from funcx.utils.response_errors import ResponseErrorCode
from tests.routes.app_test_base import AppTestBase


@pytest.fixture
def mock_user(mocker):
    return User(
        username='bob',
        globus_identity='123-456'
    )


@pytest.fixture
def mock_endpoint(mocker):
    return Endpoint(
        user_id=1,
        endpoint_uuid="11111111-2222-3333-4444-555555555555",
        restricted=True,
        restricted_functions=[]
    )


@pytest.fixture
def mock_auth_client(mocker, mock_user):
    import funcx_web_service.authentication
    mock_auth_client = mocker.Mock()
    mock_auth_client.oauth2_token_introspect = mocker.Mock(
        return_value={
            "username": "bob",
            "sub": "123-456"
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

        client = self.client

        result = client.get("/api/v1/tasks/42/status", headers={"Authorization": "my_token"})

        # Need to get mock get_redis_client working
        mock_exists.assert_called_with(None, "42")
        mock_from_id.assert_called_with(None, "42")
        assert result.json['status'] == 'ready'

    def test_register_function(self, mock_auth_client, mocker):
        mock_ingest = mocker.patch("funcx_web_service.routes.funcx.ingest_function")
        client = self.client
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
        client = self.client
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
        client = self.client
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

        saved_function = Function.find_by_uuid(result.json['function_uuid'])
        assert saved_function.container.container_id == 44

    def test_register_function_with_group_auth(self, mock_auth_client, mocker):
        mock_ingest = mocker.patch("funcx_web_service.routes.funcx.ingest_function")
        client = self.client
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

        saved_function = Function.find_by_uuid(result.json['function_uuid'])
        assert len(saved_function.auth_groups) == 1
        assert saved_function.auth_groups[0].group_id == 45

    def test_register_container(self, mocker, mock_auth_client):
        client = self.client
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
        client = self.client
        result = client.post("api/v1/containers",
                             json={
                                 "type": "docker",
                                 "location": "http://hub.docker.com/myContainer",
                             },
                             headers={"Authorization": "my_token"})
        assert result.status_code == 400
        assert result.json['status'] == 'Failed'
        assert result.json['code'] == int(ResponseErrorCode.REQUEST_KEY_ERROR)
        assert result.json['reason'] == "Missing key in JSON request - 'name'"

    def test_register_endpoint(self, mocker, mock_auth_client, mock_user):
        client = self.client

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
        client = self.client
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
        assert result.json['status'] == 'Failed'
        assert result.json['code'] == int(ResponseErrorCode.ENDPOINT_OUTDATED)
        assert "Endpoint is out of date." in result.json['reason']

    def test_register_endpoint_no_version(self, mocker, mock_auth_client):
        client = self.client
        get_forwarder_version = mocker.patch(
            "funcx_web_service.routes.funcx.get_forwarder_version",
            return_value={"min_ep_version": "1.42.0"})

        result = client.post("api/v1/register_endpoint_2",
                             json={
                             },
                             headers={"Authorization": "my_token"})
        get_forwarder_version.assert_called()
        assert result.status_code == 400
        assert result.json['status'] == 'Failed'
        assert result.json['code'] == int(ResponseErrorCode.REQUEST_KEY_ERROR)
        assert "version must be passed in" in result.json['reason']

    def test_register_endpoint_missing_keys(self, mocker, mock_auth_client):
        client = self.client

        get_forwarder_version = mocker.patch(
            "funcx_web_service.routes.funcx.get_forwarder_version",
            return_value={"min_ep_version": "1.0.0"})

        result = client.post("api/v1/register_endpoint_2",
                             json={
                                 "version": "1.0.0",
                                 "endpoint_uuid": None
                             },
                             headers={"Authorization": "my_token"})
        get_forwarder_version.assert_called()

        assert result.status_code == 400
        assert result.json['status'] == 'Failed'
        assert result.json['code'] == int(ResponseErrorCode.REQUEST_KEY_ERROR)
        assert result.json['reason'] == "Missing key in JSON request - 'endpoint_name'"

    def test_register_endpoint_already_registered(self, mocker, mock_auth_client, mock_endpoint):
        client = self.client

        get_forwarder_version = mocker.patch(
            "funcx_web_service.routes.funcx.get_forwarder_version",
            return_value={"min_ep_version": "1.0.0"})

        mocker.patch.object(Endpoint, "find_by_uuid", return_value=mock_endpoint)

        result = client.post("api/v1/register_endpoint_2",
                             json={
                                 "version": "1.0.0",
                                 "endpoint_name": "my-endpoint",
                                 "endpoint_uuid": "11111111-2222-3333-4444-555555555555"
                             },
                             headers={"Authorization": "my_token"})
        get_forwarder_version.assert_called()

        assert result.status_code == 400
        assert result.json['status'] == 'Failed'
        assert result.json['code'] == int(ResponseErrorCode.ENDPOINT_ALREADY_REGISTERED)
        assert result.json['reason'] == "Endpoint 11111111-2222-3333-4444-555555555555 was already registered by a different user"

    def test_register_endpoint_unknown_error(self, mocker, mock_auth_client):
        client = self.client

        get_forwarder_version = mocker.patch(
            "funcx_web_service.routes.funcx.get_forwarder_version",
            return_value={"min_ep_version": "1.0.0"})

        mock_register_endpoint = \
            mocker.patch("funcx_web_service.routes.funcx.register_endpoint",
                         return_value="123-45-6789-1011")
        mock_register_endpoint.side_effect = Exception("hello")

        result = client.post("api/v1/register_endpoint_2",
                             json={
                                 "version": "1.0.0",
                                 "endpoint_name": "my-endpoint",
                                 "endpoint_uuid": None
                             },
                             headers={"Authorization": "my_token"})
        get_forwarder_version.assert_called()

        assert result.status_code == 500
        assert result.json['status'] == 'Failed'
        assert result.json['code'] == int(ResponseErrorCode.UNKNOWN_ERROR)
        assert result.json['reason'] == "An unknown error occurred: hello"

    def test_submit_function_access_forbidden(self, mocker, mock_auth_client):
        client = self.client

        mock_authorize_function = mocker.patch(
            "funcx_web_service.routes.funcx.authorize_function",
            return_value=False)

        result = client.post("api/v1/submit",
                             json={'tasks': [('1111', '2222', '')]},
                             headers={"Authorization": "my_token"})

        mock_authorize_function.assert_called()

        assert result.status_code == 207
        res = result.json['results'][0]
        assert res['http_status_code'] == 403
        assert res['status'] == 'Failed'
        assert res['code'] == int(ResponseErrorCode.FUNCTION_ACCESS_FORBIDDEN)
        assert res['reason'] == "Unauthorized access to function 1111"

    def test_submit_function_not_found(self, mocker, mock_auth_client):
        client = self.client

        mock_find_function = mocker.patch(
            "funcx_web_service.authentication.auth.Function.find_by_uuid",
            return_value=None)

        result = client.post("api/v1/submit",
                             json={'tasks': [('1111', '2222', '')]},
                             headers={"Authorization": "my_token"})

        mock_find_function.assert_called()

        assert result.status_code == 207
        res = result.json['results'][0]
        assert res['http_status_code'] == 404
        assert res['status'] == 'Failed'
        assert res['code'] == int(ResponseErrorCode.FUNCTION_NOT_FOUND)
        assert res['reason'] == "Function 1111 could not be resolved"

    def test_submit_endpoint_access_forbidden(self, mocker, mock_auth_client):
        client = self.client

        mock_authorize_function = mocker.patch(
            "funcx_web_service.routes.funcx.authorize_function",
            return_value=True)

        mock_resolve_function = mocker.patch(
            "funcx_web_service.routes.funcx.resolve_function",
            return_value=('1', '2', '3'))

        mock_authorize_endpoint = mocker.patch(
            "funcx_web_service.routes.funcx.authorize_endpoint",
            return_value=False)

        result = client.post("api/v1/submit",
                             json={'tasks': [('1111', '2222', '')]},
                             headers={"Authorization": "my_token"})

        mock_authorize_function.assert_called()
        mock_resolve_function.assert_called()
        mock_authorize_endpoint.assert_called()

        assert result.status_code == 207
        res = result.json['results'][0]
        assert res['http_status_code'] == 403
        assert res['status'] == 'Failed'
        assert res['code'] == int(ResponseErrorCode.ENDPOINT_ACCESS_FORBIDDEN)
        assert res['reason'] == "Unauthorized access to endpoint 2222"

    def test_submit_endpoint_not_found(self, mocker, mock_auth_client):
        client = self.client

        mock_authorize_function = mocker.patch(
            "funcx_web_service.routes.funcx.authorize_function",
            return_value=True)

        mock_resolve_function = mocker.patch(
            "funcx_web_service.routes.funcx.resolve_function",
            return_value=('1', '2', '3'))

        mock_find_endpoint = mocker.patch(
            "funcx_web_service.authentication.auth.Endpoint.find_by_uuid",
            return_value=None)

        result = client.post("api/v1/submit",
                             json={'tasks': [('1111', '2222', '')]},
                             headers={"Authorization": "my_token"})

        mock_authorize_function.assert_called()
        mock_resolve_function.assert_called()
        mock_find_endpoint.assert_called()

        assert result.status_code == 207
        res = result.json['results'][0]
        assert res['http_status_code'] == 404
        assert res['status'] == 'Failed'
        assert res['code'] == int(ResponseErrorCode.ENDPOINT_NOT_FOUND)
        assert res['reason'] == "Endpoint 2222 could not be resolved"

    def test_submit_function_not_permitted(self, mocker, mock_auth_client, mock_endpoint):
        client = self.client

        mock_authorize_function = mocker.patch(
            "funcx_web_service.routes.funcx.authorize_function",
            return_value=True)

        mock_resolve_function = mocker.patch(
            "funcx_web_service.routes.funcx.resolve_function",
            return_value=('1', '2', '3'))

        mock_find_endpoint = mocker.patch(
            "funcx_web_service.authentication.auth.Endpoint.find_by_uuid",
            return_value=mock_endpoint)

        result = client.post("api/v1/submit",
                             json={'tasks': [('1111', '2222', '')]},
                             headers={"Authorization": "my_token"})

        mock_authorize_function.assert_called()
        mock_resolve_function.assert_called()
        mock_find_endpoint.assert_called()

        assert result.status_code == 207
        res = result.json['results'][0]
        assert res['http_status_code'] == 403
        assert res['status'] == 'Failed'
        assert res['code'] == int(ResponseErrorCode.FUNCTION_NOT_PERMITTED)
        assert res['reason'] == "Function 1111 not permitted on endpoint 2222"
