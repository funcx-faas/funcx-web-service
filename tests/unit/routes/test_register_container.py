from funcx_common.response_errors import ResponseErrorCode

from funcx_web_service.models.container import Container, ContainerImage


def test_register_container(flask_test_client, mocker, in_mock_auth_state):
    result = flask_test_client.post(
        "v2/containers",
        json={
            "name": "myContainer",
            "function_name": "test fun",
            "description": "this is a test",
            "type": "docker",
            "location": "http://hub.docker.com/myContainer",
        },
        headers={"Authorization": "my_token"},
    )
    assert result.status_code == 200
    assert "container_id" in result.json
    container_uuid = result.json["container_id"]

    saved_container = Container.find_by_uuid(container_uuid)
    assert saved_container
    assert saved_container.name == "myContainer"
    assert saved_container.container_uuid == container_uuid
    assert saved_container.description == "this is a test"

    assert saved_container.images
    assert len(saved_container.images) == 1
    assert saved_container.images[0].type == "docker"
    assert saved_container.images[0].location == "http://hub.docker.com/myContainer"
    assert saved_container.images[0].build_status == ContainerImage.BuildStates.provided


def test_register_container_invalid_spec(flask_test_client, mocker, in_mock_auth_state):
    result = flask_test_client.post(
        "v2/containers",
        json={
            "type": "docker",
            "location": "http://hub.docker.com/myContainer",
        },
        headers={"Authorization": "my_token"},
    )
    assert result.status_code == 400
    assert result.json["status"] == "Failed"
    assert result.json["code"] == int(ResponseErrorCode.REQUEST_KEY_ERROR)
    assert result.json["reason"] == "Missing key in JSON request - 'name'"


def test_get_container(flask_test_client, mocker, in_mock_auth_state):
    container = Container()
    container.container_uuid = "123-45-678"
    container.name = "Docky"
    container.images = [ContainerImage(build_status=ContainerImage.BuildStates.provided)]
    find_container_mock = mocker.patch.object(
        Container, "find_by_uuid_and_type", return_value=container
    )

    result = flask_test_client.get(
        "v2/containers/1/docker", headers={"Authorization": "my_token"}
    )

    result_container = result.json["container"]
    assert result_container["container_uuid"] == "123-45-678"
    assert result_container["build_status"] == "provided"
    find_container_mock.assert_called_with("1", "docker")


def test_get_container_build_status(flask_test_client, mocker, in_mock_auth_state):
    container = Container()
    container.container_uuid = "123-45-678"
    container.name = "Docky"
    container.build_status = ContainerImage.BuildStates.submitted
    find_container_mock = mocker.patch.object(
        Container, "find_by_uuid", return_value=container
    )

    result = flask_test_client.get(
        "v2/containers/build/1", headers={"Authorization": "my_token"}
    )

    assert result.status_code == 200
    result_status = result.json["status"]
    assert result_status == "submitted"
    find_container_mock.assert_called_with("1")


def test_get_container_build_status_not_found(
    flask_test_client, in_mock_auth_state, mocker
):
    find_container_mock = mocker.patch.object(
        Container, "find_by_uuid", return_value=None
    )

    result = flask_test_client.get(
        "v2/containers/build/1", headers={"Authorization": "my_token"}
    )

    assert result.status_code == 404
    find_container_mock.assert_called_with("1")
