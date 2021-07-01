import os
import logging
from pythonjsonlogger import jsonlogger

from funcx_web_service.routes.auth import auth_api
from flask import Flask
from funcx_web_service.routes.automate import automate_api
from funcx_web_service.routes.funcx import funcx_api


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname


def create_app(test_config=None):
    application = Flask(__name__)

    level = os.environ.get('LOGLEVEL', 'WARNING').upper()
    logger = application.logger
    handler = logging.StreamHandler()
    handler.setLevel(level)
    formatter = CustomJsonFormatter()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

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
