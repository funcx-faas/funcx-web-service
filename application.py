from flask import (Flask, request, flash, redirect, session, url_for)

from api.api import api
from api.automate_api import automate
from gui.routes import guiapi

from config import SECRET_KEY, _load_funcx_client

application = Flask(__name__)

# Include the API blueprint
application.register_blueprint(guiapi)
application.register_blueprint(api, url_prefix="/api/v1")
application.register_blueprint(automate, url_prefix="/automate")


from gui.routes import *


# Consider using @authenticated decorator so don't need to check user.
@application.route('/login', methods=['GET'])
def login():
    """Send the user to Globus Auth."""
    return redirect(url_for('callback'))


@application.route('/callback', methods=['GET'])
def callback():
    """Handles the interaction with Globus Auth."""
    # If we're coming back from Globus Auth in an error state, the error
    # will be in the "error" query string parameter.
    if 'error' in request.args:
        flash("You could not be logged into the portal: " +
              request.args.get('error_description', request.args['error']))
        return redirect(url_for('home'))

    # Set up our Globus Auth/OAuth2 state
    # redirect_uri = url_for('callback', _external=True)
    redirect_uri = 'https://funcx.org/callback'
    client = _load_funcx_client()
    client.oauth2_start_flow(redirect_uri, refresh_tokens=False)

    # If there's no "code" query string parameter, we're in this route
    # starting a Globus Auth login flow.
    if 'code' not in request.args:
        auth_uri = client.oauth2_get_authorize_url()
        return redirect(auth_uri)
    else:
        # If we do have a "code" param, we're coming back from Globus Auth
        # and can start the process of exchanging an auth code for a token.
        code = request.args.get('code')
        tokens = client.oauth2_exchange_code_for_tokens(code)
        id_token = tokens.decode_id_token(client)
        application.logger.debug(id_token)
        session.update(
            tokens=tokens.by_resource_server,
            is_authenticated=True
        )

        return redirect('https://funcx.org')


@application.route('/logout', methods=['GET'])
def logout():
    """
    - Revoke the tokens with Globus Auth.
    - Destroy the session state.
    - Redirect the user to the Globus Auth logout page.
    """
    client = _load_funcx_client()

    # Revoke the tokens with Globus Auth
    for token, token_type in (
            (token_info[ty], ty)
            # get all of the token info dicts
            for token_info in session['tokens'].values()
            # cross product with the set of token types
            for ty in ('access_token', 'refresh_token')
            # only where the relevant token is actually present
            if token_info[ty] is not None):
        client.oauth2_revoke_token(
            token, additional_params={'token_type_hint': token_type})

    # Destroy the session state
    session.clear()

    redirect_uri = url_for('home', _external=True)

    ga_logout_url = list()
    ga_logout_url.append('https://auth.globus.org/v2/web/logout')
    ga_logout_url.append('?client=6a47fd0c-6423-4851-80a2-c0947c1d884d')
    ga_logout_url.append('&redirect_uri={}'.format(redirect_uri))
    ga_logout_url.append('&redirect_name=https://funcx.org')

    # Redirect the user to the Globus Auth logout page
    return redirect(''.join(ga_logout_url))


application.secret_key = SECRET_KEY
application.config['SESSION_TYPE'] = 'filesystem'

if __name__ == "__main__":
    application.run(debug=True, host="0.0.0.0")
