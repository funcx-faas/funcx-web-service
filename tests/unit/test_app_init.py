import funcx_web_service

TEST_CONFIG = """\
FOO = "bar"
SECRET_VALUE = "blah"
BOOL_VALUE = False
CONTAINER_SERVICE_ENABLED = False
"""


def test_read_from_config(tmp_path, monkeypatch):
    conf_file = tmp_path / "test.config"
    conf_file.write_text(TEST_CONFIG)
    monkeypatch.setenv("APP_CONFIG_FILE", str(conf_file))

    app = funcx_web_service.create_app()
    assert app.config["FOO"] == "bar"
    assert app.config["SECRET_VALUE"] == "blah"
    assert not app.config["BOOL_VALUE"]

    monkeypatch.setenv("SECRET_VALUE", "shhh")
    monkeypatch.setenv("BOOL_VALUE", "true")
    app_from_env = funcx_web_service.create_app()
    assert app_from_env.config["SECRET_VALUE"] == "shhh"
    assert app_from_env.config["BOOL_VALUE"]
