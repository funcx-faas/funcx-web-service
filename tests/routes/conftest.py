import pytest

import funcx_web_service
from funcx_web_service.models.endpoint import Endpoint
from funcx_web_service.models.user import User


@pytest.fixture
def mock_auth_client(mocker, mock_user):
    mock_auth_client = mocker.Mock()
    mock_auth_client.oauth2_token_introspect = mocker.Mock(
        return_value={
            "username": "bob",
            "sub": "123-456",
            "active": True,
            "scope": "https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all",
        })

    mocker.patch.object(funcx_web_service.authentication.auth, "get_auth_client",
                        return_value=mock_auth_client)

    mocker.patch('funcx_web_service.authentication.auth.User.resolve_user', return_value=mock_user)

    return mock_auth_client


@pytest.fixture
def mock_user():
    return User(
        username='bob',
        globus_identity='123-456',
        id=22
    )


@pytest.fixture
def mock_redis(mocker):
    mock_redis_client = mocker.Mock()
    mocker.patch("funcx_web_service.routes.funcx.get_redis_client",
                 return_value=mock_redis_client)
    return mock_redis_client


@pytest.fixture
def mock_redis_pubsub(mocker):
    mock_redis_client = mocker.Mock()
    mocker.patch("funcx_web_service.routes.funcx.g_redis_pubsub",
                 return_value=mock_redis_client)
    return mock_redis_client


@pytest.fixture
def mock_endpoint():
    return Endpoint(
        user_id=1,
        endpoint_uuid="11111111-2222-3333-4444-555555555555",
        restricted=True,
        restricted_functions=[]
    )
