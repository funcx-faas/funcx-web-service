from distutils.util import strtobool

import os
import logging
from pythonjsonlogger import jsonlogger

from flask import Flask, request
from flask.logging import default_handler
from funcx_web_service.response import FuncxResponse
from funcx_web_service.routes.auth import auth_api
from funcx_web_service.routes.automate import automate_api
from funcx_web_service.routes.funcx import funcx_api
from funcx_web_service.error_responses import create_error_response


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
    return {k: (lambda key, value: _convert_string(os.environ[k]))(k, v) for (k, v)
            in app.config.items()
            if k in os.environ}


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

    application.response_class = FuncxResponse

    if test_config:
        application.config.from_mapping(test_config)
    else:
        application.config.from_envvar('APP_CONFIG_FILE')
        application.config.update(_override_config_with_environ(application))

    # 100,000 Bytes is the max content length we will log for request/response JSON
    # due to the CloudWatch max log size
    max_log_content_length = 100000

    @application.before_first_request
    def create_tables():
        from funcx_web_service.models import db
        import funcx_web_service.models.function  # NOQA F401
        import funcx_web_service.models.container  # NOQA F401
        import funcx_web_service.models.auth_groups  # NOQA F401
        import funcx_web_service.models.user  # NOQA F401
        db.init_app(application)
        db.create_all()

    # this is called before every request
    @application.before_request
    def before_request():
        # this is basic request data
        extra = {
            "path": request.path,
            "full_path": request.full_path,
            "method": request.method,
            "log_type": "before_request"
        }

        # check that the request content is not too long and avoid
        # malformed JSON errors
        if request.content_length is not None and request.content_length <= max_log_content_length:
            try:
                extra["request_json"] = request.json
            except Exception:
                pass

        # this is additional data passed into the request URL via
        # the view arguments (e.g. in '/tasks/<task_id>', the value of
        # task_id is a view argument, so this will make task_id a
        # key in view_args property of the logged JSON)
        if request.view_args:
            extra["view_args"] = request.view_args
        logger.info("before_request", extra=extra)

    # this is called only after requests that do not raise an exception
    @application.after_request
    def after_request(response):
        # this is basic request and response data
        extra = {
            "path": request.path,
            "full_path": request.full_path,
            "method": request.method,
            "log_type": "after_request"
        }

        # check that the request/response content is not too long and avoid
        # malformed JSON errors

        if request.content_length is not None and request.content_length <= max_log_content_length:
            try:
                extra["request_json"] = request.json
            except Exception:
                pass

        if response.content_length <= max_log_content_length:
            try:
                extra["response_json"] = response.json
            except Exception:
                pass

        # this is additional data passed into the request URL via
        # the view arguments (e.g. in '/tasks/<task_id>', the value of
        # task_id is a view argument, so this will make task_id a
        # key in view_args property of the logged JSON)
        if request.view_args:
            extra["view_args"] = request.view_args
        # update the logged JSON with additional data saved in the
        # response object, such as user_id
        # This fails in testing because it appears that the Flask test_client
        # uses the wrong Response class in some cases. This is fine since
        # these logs are not critical
        try:
            extra.update(response._log_data.data)
        except Exception:
            pass
        logger.info("after_request", extra=extra)
        return response

    @application.errorhandler(Exception)
    def handle_exception(e):
        logger.exception(e)
        return create_error_response(e, jsonify_response=True)

    # Include the API blueprint
    application.register_blueprint(funcx_api, url_prefix="/v2")
    # Keeping these routes for backwards compatibility on tests.
    application.register_blueprint(funcx_api, url_prefix="/v1")
    application.register_blueprint(funcx_api, url_prefix="/api/v1")
    application.register_blueprint(automate_api, url_prefix="/automate")
    application.register_blueprint(auth_api)
    return application
