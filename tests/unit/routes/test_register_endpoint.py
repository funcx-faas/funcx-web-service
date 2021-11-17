import json
import time

import responses
from funcx_common.response_errors import ResponseErrorCode

from funcx_web_service.models.endpoint import Endpoint


@responses.activate
def test_register_endpoint(flask_test_client, mocker, mock_auth_client, mock_user):
    responses.add(
        responses.GET,
        "http://192.162.3.5:8080/version",
        json={"forwarder": "1.2.3", "min_ep_version": "3.2.1"},
        status=200,
    )

    responses.add(
        responses.POST,
        "http://192.162.3.5:8080/register",
        json={"forwarder": "1.1", "min_ep_version": "1.2"},
        status=200,
    )

    mock_register_endpoint = mocker.patch(
        "funcx_web_service.routes.funcx.register_endpoint",
        return_value="123-45-6789-1011",
    )

    result = flask_test_client.post(
        "api/v1/endpoints",
        json={
            "version": "3.2.2",
            "endpoint_name": "my-endpoint",
            "endpoint_uuid": None,
        },
        headers={"Authorization": "my_token"},
    )
    assert len(responses.calls) == 2
    assert responses.calls[0].request.url == "http://192.162.3.5:8080/version"

    mock_register_endpoint.assert_called_with(
        mock_user, "my-endpoint", "", endpoint_uuid=None
    )

    assert responses.calls[1].request.url == "http://192.162.3.5:8080/register"
    assert json.loads(responses.calls[1].request.body) == {
        "endpoint_id": "123-45-6789-1011",
        "redis_address": "my-redis.com",
        "endpoint_addr": "127.0.0.1",
    }

    assert result.status_code == 200


def test_register_endpoint_version_mismatch(
    flask_test_client, mocker, mock_auth_client
):
    get_forwarder_version = mocker.patch(
        "funcx_web_service.routes.funcx.get_forwarder_version",
        return_value={"min_ep_version": "1.42.0"},
    )

    result = flask_test_client.post(
        "api/v1/endpoints",
        json={"version": "1.0.0"},
        headers={"Authorization": "my_token"},
    )
    get_forwarder_version.assert_called()
    assert result.status_code == 400
    assert result.json["status"] == "Failed"
    assert result.json["code"] == int(ResponseErrorCode.ENDPOINT_OUTDATED)
    assert "Endpoint is out of date." in result.json["reason"]


def test_register_endpoint_no_version(flask_test_client, mocker, mock_auth_client):
    get_forwarder_version = mocker.patch(
        "funcx_web_service.routes.funcx.get_forwarder_version",
        return_value={"min_ep_version": "1.42.0"},
    )

    result = flask_test_client.post(
        "api/v1/endpoints", json={}, headers={"Authorization": "my_token"}
    )
    get_forwarder_version.assert_called()
    assert result.status_code == 400
    assert result.json["status"] == "Failed"
    assert result.json["code"] == int(ResponseErrorCode.REQUEST_KEY_ERROR)
    assert "version must be passed in" in result.json["reason"]


def test_register_endpoint_missing_keys(flask_test_client, mocker, mock_auth_client):
    get_forwarder_version = mocker.patch(
        "funcx_web_service.routes.funcx.get_forwarder_version",
        return_value={"min_ep_version": "1.0.0"},
    )

    result = flask_test_client.post(
        "api/v1/endpoints",
        json={"version": "1.0.0", "endpoint_uuid": None},
        headers={"Authorization": "my_token"},
    )
    get_forwarder_version.assert_called()

    assert result.status_code == 400
    assert result.json["status"] == "Failed"
    assert result.json["code"] == int(ResponseErrorCode.REQUEST_KEY_ERROR)
    assert result.json["reason"] == "Missing key in JSON request - 'endpoint_name'"


def test_register_endpoint_already_registered(
    flask_test_client, mocker, mock_auth_client, mock_endpoint
):
    get_forwarder_version = mocker.patch(
        "funcx_web_service.routes.funcx.get_forwarder_version",
        return_value={"min_ep_version": "1.0.0"},
    )

    mocker.patch.object(Endpoint, "find_by_uuid", return_value=mock_endpoint)

    result = flask_test_client.post(
        "api/v1/endpoints",
        json={
            "version": "1.0.0",
            "endpoint_name": "my-endpoint",
            "endpoint_uuid": "11111111-2222-3333-4444-555555555555",
        },
        headers={"Authorization": "my_token"},
    )
    get_forwarder_version.assert_called()

    assert result.status_code == 400
    assert result.json["status"] == "Failed"
    assert result.json["code"] == int(ResponseErrorCode.ENDPOINT_ALREADY_REGISTERED)
    assert (
        result.json["reason"] == "Endpoint 11111111-2222-3333-4444-555555555555 "
        "was already registered by a different user"
    )


def test_register_endpoint_unknown_error(flask_test_client, mocker, mock_auth_client):
    get_forwarder_version = mocker.patch(
        "funcx_web_service.routes.funcx.get_forwarder_version",
        return_value={"min_ep_version": "1.0.0"},
    )

    mock_register_endpoint = mocker.patch(
        "funcx_web_service.routes.funcx.register_endpoint",
        return_value="123-45-6789-1011",
    )
    mock_register_endpoint.side_effect = Exception("hello")

    result = flask_test_client.post(
        "api/v1/endpoints",
        json={
            "version": "1.0.0",
            "endpoint_name": "my-endpoint",
            "endpoint_uuid": None,
        },
        headers={"Authorization": "my_token"},
    )
    get_forwarder_version.assert_called()

    assert result.status_code == 500
    assert result.json["status"] == "Failed"
    assert result.json["code"] == int(ResponseErrorCode.UNKNOWN_ERROR)
    assert result.json["reason"] == "An unknown error occurred: hello"


def test_endpoint_status(flask_test_client, mocker, mock_auth_client, mock_redis):
    mocker.patch("funcx_web_service.routes.funcx.authorize_endpoint", return_value=True)

    epid = 123
    mock_redis.lpush(f"ep_status_{epid}", json.dumps({"timestamp": time.time()}))
    lrange_spy = mocker.spy(mock_redis, "lrange")

    result = flask_test_client.get(
        f"api/v1/endpoints/{epid}/status", headers={"Authorization": "my_token"}
    )
    status_result = result.json
    assert len(status_result["logs"]) == 1
    assert status_result["status"] == "online"
    lrange_spy.assert_called_with("ep_status_123", 0, 1)


def test_endpoint_delete(flask_test_client, mocker, mock_auth_client, mock_user):
    mock_delete_endpoint = mocker.patch.object(
        Endpoint, "delete_endpoint", return_value="Ok"
    )

    result = flask_test_client.delete(
        "api/v1/endpoints/123", headers={"Authorization": "my_token"}
    )
    assert result.json["result"] == "Ok"
    mock_delete_endpoint.assert_called_with(mock_user, "123")


def test_get_whitelist(flask_test_client, mocker, mock_auth_client, mock_user):
    get_ep_whitelist = mocker.patch(
        "funcx_web_service.routes.funcx.get_ep_whitelist",
        return_value={"status": "success", "functions": ["1", "2", "3"]},
    )

    result = flask_test_client.get(
        "api/v1/endpoints/123/whitelist", headers={"Authorization": "my_token"}
    )
    whitelist_result = result.json
    assert whitelist_result["status"] == "success"
    assert whitelist_result["functions"] == ["1", "2", "3"]
    get_ep_whitelist.assert_called_with(mock_user, "123")


def test_add_whitelist(flask_test_client, mocker, mock_auth_client, mock_user):
    add_ep_whitelist = mocker.patch(
        "funcx_web_service.routes.funcx.add_ep_whitelist",
        return_value={"status": "success"},
    )

    result = flask_test_client.post(
        "api/v1/endpoints/123/whitelist",
        json={"func": ["1", "2", "3"]},
        headers={"Authorization": "my_token"},
    )
    whitelist_result = result.json
    assert whitelist_result["status"] == "success"
    add_ep_whitelist.assert_called_with(mock_user, "123", ["1", "2", "3"])


def test_delete_whitelisted(flask_test_client, mocker, mock_auth_client, mock_user):
    delete_ep_whitelist = mocker.patch(
        "funcx_web_service.routes.funcx.delete_ep_whitelist",
        return_value={"status": "success"},
    )

    result = flask_test_client.delete(
        "api/v1/endpoints/123/whitelist/678-9",
        headers={"Authorization": "my_token"},
    )
    whitelist_result = result.json
    assert whitelist_result["status"] == "success"
    delete_ep_whitelist.assert_called_with(mock_user, "123", "678-9")
