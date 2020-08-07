import os
from flask import Flask

from routes.funcx import funcx_api
from routes.automate import automate_api
from routes.auth import auth_api
from gui.routes import guiapi
from version import VERSION
from logging.config import dictConfig

from flask import Flask, render_template, request, jsonify, g
from flask_socketio import SocketIO
import redis

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


application = Flask(__name__, template_folder="gui/templates", static_folder="gui/static")
application.config.from_object(os.environ['APP_SETTINGS'])


# Include the API blueprint
application.register_blueprint(funcx_api, url_prefix="/v1")
application.register_blueprint(funcx_api, url_prefix="/api/v1")
application.register_blueprint(automate_api, url_prefix="/automate")
application.register_blueprint(auth_api)
application.register_blueprint(guiapi)


if __name__ == '__main__':
    if os.environ['FLASK_ENV'] == 'development':
        application.run("0.0.0.0", port=8080, ssl_context=("/run/secrets/web_cert", "/run/secrets/web_key"))
    else:
        application.run("0.0.0.0", port=8080)
