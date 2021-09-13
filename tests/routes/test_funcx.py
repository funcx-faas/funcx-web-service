from funcx_web_service.version import VERSION
from tests.routes.app_test_base import AppTestBase
import responses


class TestFuncX(AppTestBase):
    @responses.activate
    def test_version(self):

        responses.add(responses.GET, 'http://192.162.3.5:8080/version', json={
            'forwarder': '1.2.3',
            'min_ep_version': '3.2.1'
        }, status=200)

        client = self.client
        result = client.get("/api/v1/version", query_string={'service': "all"})
        version_result = result.json

        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == 'http://192.162.3.5:8080/version'

        assert version_result['api'] == VERSION
        assert version_result['forwarder'] == '1.2.3'
        assert version_result['min_ep_version'] == '3.2.1'

        assert "funcx" in version_result
        assert "min_sdk_version" in version_result

    def test_stats(self, mocker, mock_redis):
        mock_redis.get = mocker.Mock(return_value=1024)
        client = self.client
        result = client.get("/api/v1/stats")
        assert result.json['total_function_invocations'] == 1024
        mock_redis.get.assert_called_with('funcx_invocation_counter')
