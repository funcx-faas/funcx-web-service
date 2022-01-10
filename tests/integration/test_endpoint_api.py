import uuid

from funcx_web_service.models.user import User


def test_unauthorized_get_ep_status(
    flask_test_client, mock_auth_state, default_forwarder_responses
):
    """
    Create (register) an endpoint as one user, then switch to a second user and attempt
    to get the endpoint status.

    The result should be an error.
    """
    id1 = str(uuid.uuid1())
    id2 = str(uuid.uuid1())
    epid = str(uuid.uuid1())
    epinfo = {
        "version": "100.0.0",
        "endpoint_name": "foo-ep-1",
        "endpoint_uuid": epid,
    }

    user1 = User(username="foo", globus_identity=id1, id=100)
    user2 = User(username="bar", globus_identity=id2, id=101)

    with mock_auth_state(user=user1):
        result = flask_test_client.post("/api/v1/endpoints", json=epinfo)
        assert result.status_code == 200
    with mock_auth_state(user=user2):
        result2 = flask_test_client.get(f"/api/v1/endpoints/{epid}/status")
        assert result2.status_code == 403
