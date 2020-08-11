import os

from funcx_web_service.gui.routes import guiapi
from funcx_web_service.routes.auth import auth_api
from logging.config import dictConfig

from flask import Flask

from funcx_web_service.routes.automate import automate_api
from funcx_web_service.routes.funcx import funcx_api

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '%(module)s:%(lineno)d [%(levelname)s]: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'DEBUG',
        'handlers': ['wsgi']
    }
})


def create_app(app_config_object):
    application = Flask(__name__, template_folder="gui/templates", static_folder="gui/static")
    application.config.from_object(app_config_object)

    # Include the API blueprint
    application.register_blueprint(funcx_api, url_prefix="/v1")
    application.register_blueprint(funcx_api, url_prefix="/api/v1")
    application.register_blueprint(automate_api, url_prefix="/automate")
    application.register_blueprint(auth_api)
    application.register_blueprint(guiapi)
    return application


if __name__ == '__main__':
    app = create_app(os.environ['APP_SETTINGS'])
    app.run("0.0.0.0", port=8080)
