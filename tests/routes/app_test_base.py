import pytest


class AppTestBase:

    @pytest.fixture(autouse=True)
    def _attach_app(self, test_app):
        self._app = test_app

    def test_client(self):
        return self._app.test_client()
