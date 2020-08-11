from funcx_web_service.gui.routes import guiapi
from funcx_web_service.routes.auth import auth_api

from flask import Flask

from funcx_web_service.routes.automate import automate_api
from funcx_web_service.routes.funcx import funcx_api


def create_app(app_config_object=None):
    application = Flask(__name__, template_folder="gui/templates", static_folder="gui/static")

    if app_config_object:
        application.config.from_object(app_config_object)
    else:
        application.config.from_envvar('APP_CONFIG_FILE')

    # Include the API blueprint
    application.register_blueprint(funcx_api, url_prefix="/v1")
    application.register_blueprint(funcx_api, url_prefix="/api/v1")
    application.register_blueprint(automate_api, url_prefix="/automate")
    application.register_blueprint(auth_api)
    application.register_blueprint(guiapi)
    return application
