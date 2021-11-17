import pytest
import responses

from funcx_web_service.authentication.auth_state import (
    AuthenticationState,
    get_auth_state,
)

INTROSPECT_RESPONSE = {
    "active": True,
    "scope": "https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all",
    "sub": "79cb54bb-2296-424a-9ab2-8dabcf1457ff",
    "username": "example@globus.org",
    "name": None,
    "email": None,
    "client_id": "facd7ccc-c5f4-42aa-916b-a0e270e2c2a9",
    "aud": ["facd7ccc-c5f4-42aa-916b-a0e270e2c2a9"],
    "iss": "https://auth.globus.org",
    "exp": 1915236549,
    "iat": 1599703671,
    "nbf": 1599703671,
    "identity_set": ["79cb54bb-2296-424a-9ab2-8dabcf1457ff"],
}


@pytest.fixture
def good_introspect(mocked_responses):
    mocked_responses.add(
        responses.POST,
        "https://auth.globus.org/v2/oauth2/token/introspect",
        json=INTROSPECT_RESPONSE,
        status=200,
    )


def test_get_auth_state_no_authz_header(flask_app, flask_app_ctx):
    ctx = flask_app.test_request_context(
        headers={},  # no Authorization header
    )

    ctx.push()

    state = get_auth_state()
    assert isinstance(state, AuthenticationState)
    assert state.is_authenticated is False

    ctx.pop()


def test_get_auth_state_good_token(flask_app, flask_app_ctx, good_introspect):
    ctx = flask_app.test_request_context(headers={"Authorization": "Bearer foo"})

    ctx.push()

    state = get_auth_state()
    assert isinstance(state, AuthenticationState)
    assert state.is_authenticated is True

    assert state.username == INTROSPECT_RESPONSE["username"]
    assert state.identity_id == INTROSPECT_RESPONSE["sub"]
    state.assert_has_default_scope()

    ctx.pop()
