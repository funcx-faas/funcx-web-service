from funcx_web_service.routes.auth import auth_api
from flask import Flask
from funcx_web_service.routes.automate import automate_api
from funcx_web_service.routes.funcx import funcx_api


def create_app(test_config=None):
    application = Flask(__name__)

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
    application.register_blueprint(funcx_api, url_prefix="/v1")
    application.register_blueprint(funcx_api, url_prefix="/api/v1")
    application.register_blueprint(automate_api, url_prefix="/automate")
    application.register_blueprint(auth_api)
    return application
