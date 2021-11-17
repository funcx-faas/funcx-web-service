def test_authenticate(flask_test_client, in_mock_auth_state):
    result = flask_test_client.get("/api/v1/authenticate")
    assert result.status_code == 200
