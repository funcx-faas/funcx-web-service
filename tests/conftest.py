import fakeredis
import pytest


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
