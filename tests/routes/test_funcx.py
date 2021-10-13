import responses

from funcx_web_service.version import VERSION
from tests.routes.app_test_base import AppTestBase


class TestFuncX(AppTestBase):
    @responses.activate
    def test_version(self, mocker):

        responses.add(
            responses.GET,
            "http://192.162.3.5:8080/version",
            json={"forwarder": "1.2.3", "min_ep_version": "3.2.1"},
            status=200,
        )

        client = self.test_client(
            {
                "CONTAINER_SERVICE_ENABLED": True,
                "CONTAINER_SERVICE": "http://container-service:5000",
            }
        )

        mock_container_service = mocker.Mock()
        mock_container_service.get_version = mocker.Mock(
            return_value={"version": "3.14"}
        )
        client.application.extensions["ContainerService"] = mock_container_service
        result = client.get("/api/v1/version", query_string={"service": "all"})
        version_result = result.json

        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == "http://192.162.3.5:8080/version"

        assert version_result["api"] == VERSION
        assert version_result["forwarder"] == "1.2.3"
        assert version_result["min_ep_version"] == "3.2.1"
        assert version_result["container_service"] == "3.14"

        assert "api" in version_result
        assert "min_sdk_version" in version_result

    @responses.activate
    def test_version_no_container_service(self, mocker):

        responses.add(
            responses.GET,
            "http://192.162.3.5:8080/version",
            json={"forwarder": "1.2.3", "min_ep_version": "3.2.1"},
            status=200,
        )

        client = self.test_client({"CONTAINER_SERVICE_ENABLED": False})

        result = client.get("/api/v1/version", query_string={"service": "all"})
        version_result = result.json

        assert version_result["api"] == VERSION
        assert version_result["forwarder"] == "1.2.3"
        assert version_result["min_ep_version"] == "3.2.1"

        assert "min_sdk_version" in version_result

    def test_stats(self, mocker, mock_redis):
        mock_redis.set("funcx_invocation_counter", 1024)
        spy = mocker.spy(mock_redis, "get")

        client = self.client
        result = client.get("/api/v1/stats")
        assert result.status_code == 200
        assert result.json["total_function_invocations"] == 1024

        spy.assert_called_once_with("funcx_invocation_counter")

    def test_stats_malformed_underlying_data(self, mocker, mock_redis):
        mock_redis.set("funcx_invocation_counter", "foo")
        spy = mocker.spy(mock_redis, "get")

        client = self.client
        result = client.get("/api/v1/stats")
        assert result.status_code == 500
        assert b"Unable to get invocation count" in result.data

        spy.assert_called_once_with("funcx_invocation_counter")
