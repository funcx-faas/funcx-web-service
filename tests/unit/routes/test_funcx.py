import pytest
import responses

from funcx_web_service.version import VERSION


@responses.activate
@pytest.mark.parametrize("container_service_enabled", (True, False))
def test_version(
    flask_test_client, enable_mock_container_service, container_service_enabled
):
    responses.add(
        responses.GET,
        "http://192.162.3.5:8080/version",
        json={"forwarder": "1.2.3", "min_ep_version": "3.2.1"},
        status=200,
    )

    if container_service_enabled:
        with enable_mock_container_service():
            result = flask_test_client.get(
                "/api/v1/version", query_string={"service": "all"}
            )
    else:
        result = flask_test_client.get(
            "/api/v1/version", query_string={"service": "all"}
        )
    version_result = result.json

    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == "http://192.162.3.5:8080/version"

    assert version_result["api"] == VERSION
    assert version_result["forwarder"] == "1.2.3"
    assert version_result["min_ep_version"] == "3.2.1"
    if container_service_enabled:
        assert version_result["container_service"] == "3.14"
    else:
        assert "container_service" not in version_result

    assert "min_sdk_version" in version_result


def test_stats(flask_test_client, mocker, mock_redis):
    mock_redis.set("funcx_invocation_counter", 1024)
    spy = mocker.spy(mock_redis, "get")

    result = flask_test_client.get("/api/v1/stats")
    assert result.status_code == 200
    assert result.json["total_function_invocations"] == 1024

    spy.assert_called_once_with("funcx_invocation_counter")


def test_stats_malformed_underlying_data(flask_test_client, mocker, mock_redis):
    mock_redis.set("funcx_invocation_counter", "foo")
    spy = mocker.spy(mock_redis, "get")

    result = flask_test_client.get("/api/v1/stats")
    assert result.status_code == 500
    assert b"Unable to get invocation count" in result.data

    spy.assert_called_once_with("funcx_invocation_counter")
