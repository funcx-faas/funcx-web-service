import pytest
from funcx_web_service import create_app


@pytest.fixture(scope="session")
def test_app():
    app = create_app(
        test_config={
            "REDIS_HOST": "localhost",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "HOSTNAME": "http://testhost",
            "FORWARDER_IP": "192.162.3.5",
        }
    )
    app.secret_key = "Shhhhh"
    return app


@pytest.fixture
def test_app_context(test_app):
    with test_app.app_context():
        yield
