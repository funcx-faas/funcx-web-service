from funcx_web_service import create_app


class AppTestBase:
    def test_client(self, extra_config=None):
        test_config = {
            "REDIS_HOST": "localhost",
            "REDIS_PORT": 5000,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "HOSTNAME": "http://testhost",
            "FORWARDER_IP": "192.162.3.5",
            "ADVERTISED_REDIS_HOST": "my-redis.com",
            "CONTAINER_SERVICE_ENABLED": False,
        }

        test_config.update(extra_config if extra_config else {})
        app = create_app(test_config=test_config)
        app.secret_key = "Shhhhh"
        return app.test_client()

    def setup_method(self, method):
        self.client = self.test_client()
        self.app_context = self.client.application.app_context()
        self.app_context.push()

    def teardown_method(self, method):
        self.app_context.pop()
