import os
import logging
from pythonjsonlogger import jsonlogger

from funcx_web_service.routes.auth import auth_api
from flask import Flask
from flask.logging import default_handler
from funcx_web_service.routes.automate import automate_api
from funcx_web_service.routes.funcx import funcx_api


def create_app(test_config=None):
    application = Flask(__name__)

    level = os.environ.get('LOGLEVEL', 'DEBUG').upper()
    logger = application.logger
    logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # This removes the default Flask handler. Since we have added a JSON
    # log formatter and handler above, we must disable the default handler
    # to prevent duplicate log messages (where one is the normal log format
    # and the other is JSON format).
    logger.removeHandler(default_handler)

    if test_config:
        application.config.from_mapping(test_config)
    else:
        application.config.from_envvar('APP_CONFIG_FILE')

    @application.before_first_request
    def create_tables():
        from funcx_web_service.models import db
        import funcx_web_service.models.function  # NOQA F401
        import funcx_web_service.models.container # NOQA F401
        import funcx_web_service.models.auth_groups # NOQA F401
        import funcx_web_service.models.user # NOQA F401
        db.init_app(application)
        db.create_all()

    # Include the API blueprint
    application.register_blueprint(funcx_api, url_prefix="/v2")
    # Keeping these routes for backwards compatibility on tests.
    application.register_blueprint(funcx_api, url_prefix="/v1")
    application.register_blueprint(funcx_api, url_prefix="/api/v1")
    application.register_blueprint(automate_api, url_prefix="/automate")
    application.register_blueprint(auth_api)
    return application
