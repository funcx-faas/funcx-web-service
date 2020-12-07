from funcx_web_service.authentication.auth import get_auth_client, FUNCX_SCOPE
from funcx_web_service.models.user import User
from flask import request, flash, redirect, session, url_for, Blueprint, current_app as app

auth_api = Blueprint("auth_api", __name__)
FUNCX_SCOPE = 'https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all'

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
    redirect_uri = f"{app.config['HOSTNAME']}/callback"
    client = get_auth_client()
    requested_scopes = [app.config.get('FUNCX_SCOPE', FUNCX_SCOPE), 'profile',
                        'urn:globus:auth:scope:transfer.api.globus.org:all',
                        'urn:globus:auth:scope:auth.globus.org:view_identities', 'openid']
    client.oauth2_start_flow(redirect_uri, requested_scopes=requested_scopes, refresh_tokens=False)

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
        app.logger.debug(tokens)
        id_token = tokens.decode_id_token(client)

        # Make sure the user exists in the database
        user_id = User.resolve_user(id_token.get('preferred_username'))

        session.update(
            tokens=tokens.by_resource_server,
            username=id_token.get('preferred_username'),
            user_id=user_id.id,
            name=id_token.get('name'),
            email=id_token.get('email'),
            is_authenticated=True
        )

        return redirect('https://dev.funcx.org/home')


@auth_api.route('/logout', methods=['GET'])
def logout():
    """
    - Revoke the tokens with Globus Auth.
    - Destroy the session state.
    - Redirect the user to the Globus Auth logout page.
    """
    client = get_auth_client()

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

    ga_logout_url = list()
    ga_logout_url.append('https://auth.globus.org/v2/web/logout')
    ga_logout_url.append('?client=6a47fd0c-6423-4851-80a2-c0947c1d884d')
    ga_logout_url.append('&redirect_uri=https://dev.funcx.org')
    ga_logout_url.append('&redirect_name=https://dev.funcx.org')

    # Redirect the user to the Globus Auth logout page
    return redirect(''.join(ga_logout_url))
