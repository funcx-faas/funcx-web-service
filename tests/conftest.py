import contextlib
import typing as t
import uuid

import boto3
import fakeredis
import flask
import moto
import pytest
import responses

from funcx_web_service import create_app
from funcx_web_service.models.user import User

TEST_FORWARDER_IP = "192.162.3.5"
DEFAULT_FUNCX_SCOPE = (
    "https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all"
)


class FakeAuthState:
    """A fake object to replace the AuthenticationState during tests."""

    def __init__(
        self,
        *,
        user: t.Optional[User],
        scope: t.Optional[str],
        introspect_data: t.Optional[dict],
    ):
        self.is_authenticated = user is not None
        self.user_object = user
        self.username = user.username if user is not None else None
        self.identity_id = user.globus_identity if user is not None else None
        self.scopes = {scope}

        if introspect_data is None:
            if self.is_authenticated:
                self.introspect_data = {
                    "active": True,
                    "username": self.username,
                    "sub": self.identity_id,
                    "scope": scope,
                }
            else:
                self.introspect_data = {"active": False}
        else:
            self.introspect_data = introspect_data

    def assert_is_authenticated(self):
        if not self.is_authenticated:
            flask.abort(401, "unauthenticated in FakeAuthState")

    def assert_has_default_scope(self):
        if DEFAULT_FUNCX_SCOPE not in self.scopes:
            flask.abort(403, "missing scope in FakeAuthState")


@pytest.fixture
def mocked_responses():
    with responses.RequestsMock() as r:
        yield r


@pytest.fixture
def mock_redis_server():
    return fakeredis.FakeServer()


@pytest.fixture
def mock_redis_pubsub(mocker):
    mock_pubsub = mocker.Mock()

    mocker.patch(
        "funcx_web_service.routes.funcx.g_redis_pubsub", return_value=mock_pubsub
    )
    return mock_pubsub


@pytest.fixture
def mock_redis(mocker, mock_redis_server):
    mock_redis_client = fakeredis.FakeStrictRedis(
        server=mock_redis_server, decode_responses=True
    )

    mocker.patch(
        "funcx_web_service.routes.funcx.get_redis_client",
        return_value=mock_redis_client,
    )

    return mock_redis_client


@pytest.fixture(scope="session")
def flask_app():
    app = create_app(
        test_config={
            "GLOBUS_CLIENT": "TEST_GLOBUS_CLIENT_ID",
            "GLOBUS_KEY": "TEST_GLOBUS_CLIENT_SECRET",
            "REDIS_HOST": "localhost",
            "REDIS_PORT": 5000,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "HOSTNAME": "http://testhost",
            "FORWARDER_IP": TEST_FORWARDER_IP,
            "ADVERTISED_REDIS_HOST": "my-redis.com",
            "CONTAINER_SERVICE_ENABLED": False,
        }
    )
    app.secret_key = "Shhhhh"
    return app


@pytest.fixture
def flask_app_ctx(flask_app):
    with flask_app.app_context() as app_ctx:
        yield app_ctx


@pytest.fixture
def flask_request_ctx(flask_app, flask_app_ctx):
    with flask_app.test_request_context() as request_ctx:
        yield request_ctx


@pytest.fixture
def flask_test_client(flask_app, flask_app_ctx):
    return flask_app.test_client()


@pytest.fixture
def enable_mock_container_service(flask_app, mocker):
    mock_container_service = mocker.Mock()
    mock_container_service.get_version = mocker.Mock(return_value={"version": "3.14"})

    @contextlib.contextmanager
    def func():
        flask_app.extensions["ContainerService"] = mock_container_service
        flask_app.config["CONTAINER_SERVICE_ENABLED"] = True

        yield

        flask_app.extensions["ContainerService"] = None
        flask_app.config["CONTAINER_SERVICE_ENABLED"] = False

    return func


@pytest.fixture
def mock_s3_bucket(monkeypatch):
    bucket = "funcx-web-service-test-bucket"
    monkeypatch.setenv("FUNCX_S3_BUCKET_NAME", bucket)
    with moto.mock_s3():
        client = boto3.client("s3")
        client.create_bucket(Bucket=bucket)
        yield bucket


@pytest.fixture
def mock_user_identity_id():
    return str(uuid.uuid1())


@pytest.fixture
def mock_user(flask_app_ctx, mock_user_identity_id):
    return User(username="foo-user", globus_identity=mock_user_identity_id, id=22)


@pytest.fixture
def mock_auth_state(flask_request_ctx, mock_user, mock_user_identity_id):
    # this fixture returns a context manager which can be used to set a mocked state
    # by default, that context manager will use the mock_user fixture data

    @contextlib.contextmanager
    def mock_ctx(*, user=mock_user, scope=DEFAULT_FUNCX_SCOPE, introspect_data=None):
        fake_auth_state = FakeAuthState(
            user=user,
            scope=scope,
            introspect_data=introspect_data,
        )

        sentinel = object()
        oldstate = getattr(flask.g, "auth_state", sentinel)
        flask.g.auth_state = fake_auth_state
        yield
        if oldstate is sentinel:
            delattr(flask.g, "auth_state")
        else:
            flask.g.auth_state = oldstate

    return mock_ctx


@pytest.fixture
def in_mock_auth_state(mock_auth_state):
    """
    A slightly different fixture from the mock_auth_state, this enters the
    context manager provided by mock_auth_state automatically.
    """
    with mock_auth_state():
        yield


@pytest.fixture
def default_forwarder_responses(mocked_responses):
    mocked_responses.add(
        responses.GET,
        f"http://{TEST_FORWARDER_IP}:8080/version",
        json={
            "forwarder": "0.3.5",
            "min_ep_version": "0.0.1",
        },
        status=200,
    )
    mocked_responses.add(
        responses.POST,
        f"http://{TEST_FORWARDER_IP}:8080/register",
        body="{}",
        status=200,
    )
