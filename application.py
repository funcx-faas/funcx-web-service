import os
from flask import Flask

from routes.funcx import funcx_api
from routes.automate import automate_api
from routes.auth import auth_api

application = Flask(__name__)

application.config.from_object(os.environ['APP_SETTINGS'])

# Include the API blueprint
application.register_blueprint(funcx_api, url_prefix="/api/v1")
application.register_blueprint(automate_api, url_prefix="/automate")
application.register_blueprint(auth_api)


@application.route("/")
def home():
    # TODO: Remove this once the GUI is deployed.
    application.logger.debug("FuncX")
    return "funcX"


if __name__ == "__main__":
    application.run(debug=True, host="0.0.0.0")
