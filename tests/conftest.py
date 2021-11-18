import contextlib

import fakeredis
import pytest

from funcx_web_service import create_app


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
            "REDIS_HOST": "localhost",
            "REDIS_PORT": 5000,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "HOSTNAME": "http://testhost",
            "FORWARDER_IP": "192.162.3.5",
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
