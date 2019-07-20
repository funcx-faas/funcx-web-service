from flask import Flask

from api.api import api
from api.automate_api import automate
from api.auth import auth_api

from config import SECRET_KEY

application = Flask(__name__)

# Include the API blueprint
application.register_blueprint(api, url_prefix="/api/v1")
application.register_blueprint(automate, url_prefix="/automate")
application.register_blueprint(auth_api)


@application.route("/")
def home():
    # TODO: Remove this once the GUI is deployed.
    application.logger.debug("FuncX")
    return "funcX"


application.secret_key = SECRET_KEY
application.config['SESSION_TYPE'] = 'filesystem'


if __name__ == "__main__":
    application.run(debug=True, host="0.0.0.0")
