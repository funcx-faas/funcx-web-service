from funcx_common.response_errors import ResponseErrorCode
from funcx_web_service.models.tasks import TaskGroup
from tests.routes.app_test_base import AppTestBase


class TestSubmitFunction(AppTestBase):

    def test_submit_function_access_forbidden(self, mocker, mock_auth_client):
        client = self.client

        mock_authorize_function = mocker.patch(
            "funcx_web_service.routes.funcx.authorize_function",
            return_value=False)

        mocker.patch.object(TaskGroup, attribute='exists', return_value=False)

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

        mocker.patch.object(TaskGroup, attribute='exists', return_value=False)

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

        mocker.patch.object(TaskGroup, attribute='exists', return_value=False)

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

        mocker.patch.object(TaskGroup, attribute='exists', return_value=False)

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

        mocker.patch.object(TaskGroup, attribute='exists', return_value=False)

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
