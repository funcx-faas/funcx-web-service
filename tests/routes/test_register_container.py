from funcx_common.response_errors import ResponseErrorCode

from funcx_web_service.models.container import Container
from tests.routes.app_test_base import AppTestBase


class TestRegisterContainer(AppTestBase):
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
