import typing as t

import globus_sdk
from flask import abort, current_app, g, request

from funcx_web_service.models.user import User

from .globus_auth import introspect_token


class AuthenticationState:
    """
    This is a dedicated object for handling authentication.

    It takes in a Globus Auth token and resolve it to a user and various data about that
    user. It is the "auth_state" object for the application within the context of a
    request, showing "who" is calling the application (e.g. identity_id) and some
    information about "how" the call is being made (e.g. scopes).

    For the most part, this should not handle authorization checks, to maintain
    separation of concerns.
    """

    # Default scope if not provided in config
    DEFAULT_FUNCX_SCOPE = (
        "https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all"
    )

    def __init__(
        self, token: t.Optional[str], *, assert_default_scope: bool = True
    ) -> None:
        self.funcx_all_scope: str = current_app.config.get(
            "FUNCX_SCOPE", self.DEFAULT_FUNCX_SCOPE
        )
        self.token = token

        self.introspect_data: t.Optional[globus_sdk.GlobusHTTPResponse] = None
        self.identity_id: t.Optional[str] = None
        self.username: t.Optional[str] = None
        self._user_object: t.Optional[User] = None
        self.scopes: t.Set[str] = set()

        if token:
            self._handle_token()

    def _handle_token(self) -> None:
        """Given a token, flesh out the AuthenticationState."""
        self.introspect_data = introspect_token(t.cast(str, self.token))
        self.username = self.introspect_data["username"]
        self.identity_id = self.introspect_data["sub"]
        self.scopes = set(self.introspect_data["scope"].split(" "))

    @property
    def user_object(self) -> User:
        if self._user_object is None:
            self._user_object = User.resolve_user(self.username)
        return self._user_object

    @property
    def is_authenticated(self):
        return self.identity_id is not None

    def assert_is_authenticated(self):
        """
        This tests that is_authenticated=True, and raises an Unauthorized error
        (401) if it is not.
        """
        if not self.is_authenticated:
            abort(401, "method requires token authenticated access")

    def assert_has_scope(self, scope: str) -> None:
        # the user may be thought of as "not properly authorized" if they do not have
        # required scopes
        # this leaves a question of whether this should be a 401 (Unauthorized) or
        # 403 (Forbidden)
        #
        # the answer is that it must be a 403
        # this requirement is set by the OAuth2 spec
        #
        # for more detail, see
        #   https://datatracker.ietf.org/doc/html/rfc6750#section-3.1
        if scope not in self.scopes:
            abort(403, "Missing Scopes")

    def assert_has_default_scope(self) -> None:
        self.assert_has_scope(self.funcx_all_scope)


def get_auth_state():
    """
    Get the current AuthenticationState. This may be called at any time in the
    application within a request context, but will always return the same state object.

    It is especially useful for tests, which can mock over the return value of this
    function by setting `g.auth_state` and be assured that the application will respect
    the fake authentication info.
    """
    if not g.get("auth_state", None):
        cred = request.headers.get("Authorization", None)
        if cred and cred.startswith("Bearer "):
            cred = cred[7:]
        else:
            cred = None

        g.auth_state = AuthenticationState(cred)
    return g.auth_state
