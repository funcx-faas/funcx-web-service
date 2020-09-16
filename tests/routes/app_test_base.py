from funcx_web_service import create_app


class AppTestBase:
    def test_client(self):
        app = create_app(test_config={
            "REDIS_HOST": "localhost",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "HOSTNAME": "http://testhost"
        })
        app.secret_key = "Shhhhh"
        return app.test_client()
