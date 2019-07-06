from flask import (Flask, request, flash, redirect, session, url_for)

#from api.api import api
#from api.automate_api import automate

from config import SECRET_KEY, _load_funcx_client

#import logging

application = Flask(__name__)


# Include the API blueprint
#app.register_blueprint(api, url_prefix="/api/v1")
#app.register_blueprint(automate, url_prefix="/automate")

@application.route("/")
def hello():
    application.logger.debug("FuncX")
    return "Funcx"


if __name__ == "__main__":
    application.run(debug=True, host="0.0.0.0")

