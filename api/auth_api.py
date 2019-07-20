from config import _load_funcx_client
from flask import request, flash, redirect, session, url_for, Blueprint

auth_api = Blueprint("auth_api", __name__)


@auth_api.route('/login', methods=['GET'])
def login():
    """Send the user to Globus Auth."""
    return redirect(url_for('auth_api.callback'))


@auth_api.route('/callback', methods=['GET'])
def callback():
    """Handles the interaction with Globus Auth."""
    # If we're coming back from Globus Auth in an error state, the error
    # will be in the "error" query string parameter.
    if 'error' in request.args:
        flash("You could not be logged into funcX: " +
              request.args.get('error_description', request.args['error']))
        return redirect(url_for('home'))

    # Set up our Globus Auth/OAuth2 state
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
        session.update(
            tokens=tokens.by_resource_server,
            is_authenticated=True
        )

        return redirect('https://funcx.org')


@auth_api.route('/logout', methods=['GET'])
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
