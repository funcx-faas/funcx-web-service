from tests.routes.app_test_base import AppTestBase


class TestAuth(AppTestBase):
    def test_authenticate(self, mock_auth_client):
        client = self.client
        result = client.get(
            "/api/v1/authenticate", headers={"Authorization": "my_token"}
        )
        assert result.status_code == 200
