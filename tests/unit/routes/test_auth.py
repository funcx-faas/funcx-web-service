def test_authenticate(flask_test_client, mock_auth_client):
    result = flask_test_client.get(
        "/api/v1/authenticate", headers={"Authorization": "my_token"}
    )
    assert result.status_code == 200
