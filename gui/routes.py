from flask import flash, redirect, render_template, request, session, url_for
from datetime import datetime, timezone
import requests
import math
from math import *
from gui import app, db
# from gui.models import User, Function
from gui.forms import EditForm
import globus_sdk

def load_app_client():
    """Create an AuthClient for the portal"""
    app = globus_sdk.ConfidentialAppAuthClient('978450b9-b2d4-41dd-a12a-2785ec1b9206','3hPNqGDocBENKgvf7N8j58uL3NimZJ8GRPN4cIc4Lus=')
    return app

@app.route('/')
def start():
    return render_template('start.html')

@app.route('/home')
def home():
    return render_template('home.html', title='Home')

@app.route('/login')
def login():
    # app.secret_key = "secret"
    """
    Login via Globus Auth.
    May be invoked in one of two scenarios:

     1. Login is starting, no state in Globus Auth yet
     2. Returning to application during login, already have short-lived
        code from Globus Auth to exchange for tokens, encoded in a query
        param
    """
    # the redirect URI, as a complete URI (not relative path)
    redirect_uri = url_for('login', _external=True)
    scopes = ("urn:globus:auth:scope:transfer.api.globus.org:all "
                  "urn:globus:auth:scope:auth.globus.org:view_identities "
                  "openid email profile")
    client = load_app_client()
    client.oauth2_start_flow(redirect_uri=redirect_uri,requested_scopes=scopes,refresh_tokens=True)
#    with open("tokens.json", 'w') as f:
#        json.dump(tokens, f)
   # If there's no "code" query string parameter, we're in this route
   # starting a Globus Auth login flow.
   # Redirect out to Globus Auth
    if 'code' not in request.args:
        auth_uri = client.oauth2_get_authorize_url()
        return redirect(auth_uri)
   # If we do have a "code" param, we're coming back from Globus Auth
   # and can start the process of exchanging an auth code for a token.
    else:
       code = request.args.get('code')
       tokens = client.oauth2_exchange_code_for_tokens(code) #
       print(tokens)
       id_token = tokens.decode_id_token(client)
       session.update(
           tokens=tokens.by_resource_server,
           is_authenticated=True,
           name=id_token.get('name', ''),
           email=id_token.get('email', ''),
           institution=id_token.get('institution', ''),
           primary_username=id_token.get('preferred_username'),
           primary_identity=id_token.get('sub'),
       )

       transfer_tokens = tokens.by_resource_server['transfer.api.globus.org']
       payload =  {"access_token": transfer_tokens['access_token'],
                  "User": id_token.get('preferred_username'),
                  "refresh_token": transfer_tokens['refresh_token'],
                  "expires_at_seconds": transfer_tokens['expires_at_seconds']}
       print (payload)
       # register this data with the service
       r = requests.post("https://m0vc2icw3m.execute-api.us-east-1.amazonaws.com/LATEST/get_user", json=payload)

       return redirect('/home')


@app.route('/logout', methods=['GET'])
# @authenticated
def logout():
   """
   - Revoke the tokens with Globus Auth.
   - Destroy the session state.
   - Redirect the user to the Globus Auth logout page.
   """
   client = load_app_client()

   # Revoke the tokens with Globus Auth
   # for token, token_type in (
   #         (token_info[ty], ty)
   #         # get all of the token info dicts
   #         for token_info in session['tokens'].values()
   #         # cross product with the set of token types
   #         for ty in ('access_token', 'refresh_token')
   #         # only where the relevant token is actually present
   #         if token_info[ty] is not None):
   #     client.oauth2_revoke_token(
   #         token, additional_params={'token_type_hint': token_type})

   # Destroy the session state
   session.clear()

   redirect_uri = '/' #url_for('home', _external=True)

   ga_logout_url = []
   ga_logout_url.append('https://auth.globus.org/v2/web/logout')
   ga_logout_url.append('?client=6a47fd0c-6423-4851-80a2-c0947c1d884d')
   ga_logout_url.append('&redirect_uri={}'.format(redirect_uri))
   ga_logout_url.append('&redirect_name=Ripple')

   # Redirect the user to the Globus Auth logout page
   return redirect(''.join(ga_logout_url))

@app.route('/functions')
def functions():
    functions = Function.query.order_by(Function.date_created).all()
    # length = len(functions)
    # numPages = ceil(length/12)
    return render_template('functions.html', title='Your Functions', functions=functions)

@app.route('/new', methods=['GET', 'POST'])
def new():
    form = EditForm()
    if form.validate_on_submit():
        func = Function(title=form.title.data, language=form.language.data, content=form.content.data)
        try:
            db.session.add(func)
            db.session.commit()
            flash(f'Saved Function "{func.title}"!', 'success')
            return redirect('../view/' + str(func.id))
        except:
            flash('There was an issue handling your request', 'danger')
    form.title.data = ""
    form.language.data = "Python 3"
    return render_template('edit.html', title='New Function', form=form, cancel_route="functions")

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    func = Function.query.get_or_404(id)
    form = EditForm()
    if form.validate_on_submit():
        func.title = form.title.data
        func.language = form.language.data
        func.content = form.content.data
        func.date_edited = datetime.now(timezone.utc)
        try:
            db.session.commit()
            flash(f'Saved Function "{func.title}"!', 'success')
            return redirect('../view/' + str(func.id))
        except:
            flash('There was an issue handling your request.', 'danger')
    form.title.data = func.title
    form.language.data = func.language
    form.content.data = func.content
    return render_template('edit.html', title=f'Edit "{func.title}"', func=func, form=form, cancel_route="view")

@app.route('/view/<int:id>')
def view(id):
    func = Function.query.get_or_404(id)
    return render_template('view.html', title=f'View "{func.title}"', func=func)

@app.route('/delete/<int:id>')
def delete(id):
    func = Function.query.get_or_404(id)
    try:
        db.session.delete(func)
        db.session.commit()
        flash(f'Deleted Function "{func.title}".', 'success')
    except:
        flash('There was an issue handling your request.', 'danger')
    return redirect(url_for('functions'))