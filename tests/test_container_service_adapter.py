import responses

from funcx_web_service import ContainerServiceAdapter


class TestContainerServiceAdapter:
    @responses.activate
    def test_version(self):
        responses.add(
            responses.GET,
            "http://container-service:5000/version",
            json={"version": "3.14"},
            status=200,
        )
        container_service = ContainerServiceAdapter("http://container-service:5000")
        assert container_service.get_version() == {"version": "3.14"}

    @responses.activate
    def test_version_server_error(self):
        responses.add(
            responses.GET, "http://container-service:5000/version", status=500
        )
        container_service = ContainerServiceAdapter("http://container-service:5000")
        assert container_service.get_version() == {"version": "Service Unavailable"}
