from funcx_web_service.version import VERSION
from tests.routes.app_test_base import AppTestBase


class TestFuncX(AppTestBase):
    def test_version(self, mocker):
        mock_get_response = mocker.Mock()
        mock_get_response.json = mocker.Mock(return_value={
            "forwarder": "1.1",
            "min_ep_version": "1.2"
        })
        mocker.patch('funcx_web_service.routes.funcx.requests.get', return_value=mock_get_response)
        client = self.client
        result = client.get("/api/v1/version", query_string={'service': "all"})
        version_result = result.json
        assert version_result['api'] == VERSION
        assert version_result['forwarder'] == '1.1'
        assert version_result['min_ep_version'] == '1.2'

        assert "funcx" in version_result
        assert "min_sdk_version" in version_result

    def test_stats(self, mocker, mock_redis):
        mock_redis.get = mocker.Mock(return_value=1024)
        client = self.client
        result = client.get("/api/v1/stats")
        assert result.json['total_function_invocations'] == 1024
        mock_redis.get.assert_called_with('funcx_invocation_counter')
