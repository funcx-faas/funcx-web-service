import logging
import os
from distutils.util import strtobool

from flask import Flask
from flask.logging import default_handler
from pythonjsonlogger import jsonlogger

from funcx_web_service.container_service_adapter import ContainerServiceAdapter
from funcx_web_service.error_responses import create_error_response
from funcx_web_service.models import db, load_all_models
from funcx_web_service.response import FuncxResponse
from funcx_web_service.routes.container import container_api
from funcx_web_service.routes.funcx import funcx_api


def _override_config_with_environ(app):
    """
    Use app.config as a guide to configuration settings that can be overridden from env
    vars.
    """
    # Env vars will be strings. Convert boolean values
    def _convert_string(value):
        return value if value not in ["true", "false"] else strtobool(value)

    # Create a dictionary of environment vars that have keys that match keys from the
    # loaded config. These will override anything from the config file
    return {
        k: (lambda key, value: _convert_string(os.environ[k]))(k, v)
        for (k, v) in app.config.items()
        if k in os.environ
    }


def create_app(test_config=None):
    application = Flask(__name__)

    level = os.environ.get("LOGLEVEL", "DEBUG").upper()
    logger = application.logger
    logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # This removes the default Flask handler. Since we have added a JSON
    # log formatter and handler above, we must disable the default handler
    # to prevent duplicate log messages (where one is the normal log format
    # and the other is JSON format).
    logger.removeHandler(default_handler)

    application.response_class = FuncxResponse

    if test_config:
        application.config.from_mapping(test_config)
    else:
        application.config.from_envvar("APP_CONFIG_FILE")
        application.config.update(_override_config_with_environ(application))

    if not hasattr(application, "extensions"):
        application.extensions = {}

    if application.config.get("CONTAINER_SERVICE_ENABLED", False):
        container_service = ContainerServiceAdapter(
            application.config["CONTAINER_SERVICE"]
        )
        application.extensions["ContainerService"] = container_service
    else:
        application.extensions["ContainerService"] = None

    load_all_models()
    db.init_app(application)

    @application.before_first_request
    def create_tables():
        db.create_all()

    @application.errorhandler(Exception)
    def handle_exception(e):
        logger.exception(e)
        return create_error_response(e, jsonify_response=True)

    # Include the API blueprint
    application.register_blueprint(funcx_api, url_prefix="/v2")
    application.register_blueprint(container_api, url_prefix="/v2")
    # Keeping these routes for backwards compatibility on tests.
    application.register_blueprint(funcx_api, url_prefix="/v1")
    application.register_blueprint(funcx_api, url_prefix="/api/v1")
    return application
