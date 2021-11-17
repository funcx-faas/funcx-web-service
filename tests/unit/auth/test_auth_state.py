import pytest
import responses
from werkzeug.exceptions import Forbidden, Unauthorized

from funcx_web_service.authentication.auth_state import (
    AuthenticationState,
    get_auth_state,
)
from funcx_web_service.models.user import User

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


@pytest.fixture
def badscope_introspect(mocked_responses):
    data = {**INTROSPECT_RESPONSE}
    data["scope"] = ""
    mocked_responses.add(
        responses.POST,
        "https://auth.globus.org/v2/oauth2/token/introspect",
        json=data,
        status=200,
    )


def test_get_auth_state_no_authz_header(flask_app, flask_app_ctx):
    # this test uses a customized flask request context in order to test get_auth_state
    # codepaths
    # this generally is not necessary to imitate: simply construct an
    # AuthenticationState in tests instead
    ctx = flask_app.test_request_context(headers={})
    ctx.push()

    state = get_auth_state()
    assert isinstance(state, AuthenticationState)
    assert state.is_authenticated is False

    with pytest.raises(Unauthorized):
        state.assert_is_authenticated()

    ctx.pop()


def test_get_auth_state_good_token(flask_app, flask_app_ctx, good_introspect):
    # this test uses a customized flask request context in order to test get_auth_state
    # codepaths
    # this generally is not necessary to imitate: simply construct an
    # AuthenticationState in tests instead
    ctx = flask_app.test_request_context(headers={"Authorization": "Bearer foo"})
    ctx.push()

    state = get_auth_state()
    assert isinstance(state, AuthenticationState)
    assert state.is_authenticated is True

    assert state.username == INTROSPECT_RESPONSE["username"]
    assert state.identity_id == INTROSPECT_RESPONSE["sub"]

    state.assert_is_authenticated()
    state.assert_has_default_scope()

    ctx.pop()


def test_auth_state_bad_scope(flask_request_ctx, badscope_introspect):
    state = AuthenticationState("foo")
    assert isinstance(state, AuthenticationState)
    assert state.is_authenticated is True
    assert state.username == INTROSPECT_RESPONSE["username"]
    assert state.identity_id == INTROSPECT_RESPONSE["sub"]

    # TODO: is this right? seems like this should be a class of 401
    with pytest.raises(Forbidden):
        state.assert_has_default_scope()


def test_auth_state_user_object(flask_request_ctx, good_introspect):
    # check that fetching a user object from the AuthenticationState works
    state = AuthenticationState("foo")

    userobj = state.user_object
    assert userobj is not None
    assert isinstance(userobj, User)
    assert userobj.username == state.username
