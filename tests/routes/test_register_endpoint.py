from funcx_common.response_errors import ResponseErrorCode

from funcx_web_service.models.endpoint import Endpoint
from tests.routes.app_test_base import AppTestBase


class TestRegisterEndpoint(AppTestBase):
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

        result = client.post("api/v1/endpoints",
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

        result = client.post("api/v1/endpoints",
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

        result = client.post("api/v1/endpoints",
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

        result = client.post("api/v1/endpoints",
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

        result = client.post("api/v1/endpoints",
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

        result = client.post("api/v1/endpoints",
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
