from flask import (abort, Blueprint, current_app as app, flash, jsonify,
                   redirect, render_template, request, session, url_for)
import uuid
from gui.forms import EditForm
from models.utils import get_db_connection, register_function
from authentication.auth import authenticated

# Flask
guiapi = Blueprint("guiapi", __name__)


@guiapi.route('/')
def start():
    return render_template('start.html')


@guiapi.route('/debug')
def debug():
    session.update(
        username='ryan@globusid.org',
        name='Ryan Chard'
    )
    return jsonify({'username': session.get("username")})


@guiapi.route('/home')
# @authenticated
def home():
    return render_template('home.html', user=session.get('name'), title='Home')


@guiapi.route('/error')
def error():
    return render_template('error.html', user=session.get('name'), title='Page Not Found')



@guiapi.route('/functions')
#@authenticated
def functions():
    # functions = Function.query.order_by(Function.date_created).all()
    # length = len(functions)
    # numPages = ceil(length/12)
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT function_name, timestamp, modified_at, function_uuid FROM functions, users WHERE functions.user_id = users.id AND users.username = %s AND functions.deleted = False", (session.get("username"),))
        functions = cur.fetchall()
    except:
        flash('There was an issue handling your request', 'danger')
        return redirect(url_for('guiapi.home'))
    return render_template('functions.html', user=session.get('name'), title='Your Functions', functions=functions)


def getUUID():
    return str(uuid.uuid4())


@guiapi.route('/new', methods=['GET', 'POST'])
# @authenticated
def new():
    form = EditForm()
    if form.validate_on_submit():
        name = form.name.data
        try:
            uuid = register_function(session.get('username'), name, form.desc.data, form.code.data, form.entry_point.data, None)
            flash(f'Saved Function "{name}"!', 'success')
            return redirect(url_for('guiapi.view', uuid=uuid))
        except:
            flash('There was an issue handling your request', 'danger')
    return render_template('edit.html', user=session.get('name'), title='New Function', form=form, cancel_route="functions")


@guiapi.route('/edit/<uuid>', methods=['GET', 'POST'])
# @authenticated
def edit(uuid):
    conn, cur = get_db_connection()
    cur.execute("SELECT function_name, description, entry_point, username, timestamp, modified_at, function_uuid, status, function_code FROM functions, users WHERE function_uuid = %s AND functions.user_id = users.id", (uuid,))
    func = cur.fetchone()
    name = func['function_name']
    form = EditForm()
    if form.validate_on_submit():
        try:
            cur.execute("UPDATE functions SET function_name = %s, description = %s, entry_point = %s, modified_at = 'NOW()', function_code = %s WHERE uuid = %s", (form.name.data, form.desc.data, form.entry_point.data, form.code.data, uuid))
            conn.commit()
            flash(f'Saved Function "{name}"!', 'success')
            return redirect(url_for('guiapi.view', uuid=uuid))
        except:
            flash('There was an issue handling your request.', 'danger')
    form.name.data = func['function_name']
    form.desc.data = func['description']
    form.entry_point.data = func['entry_point']
    form.code.data = func['function_code']
    return render_template('edit.html', user=session.get('name'), title=f'Edit "{form.name.data}"', func=func, form=form, cancel_route="view")


@guiapi.route('/view/<uuid>')
# @authenticated
def view(uuid):
    conn, cur = get_db_connection()
    cur.execute("SELECT function_name, description, entry_point, username, timestamp, modified_at, function_uuid, status, function_code FROM functions, users WHERE function_uuid = %s AND functions.user_id = users.id", (uuid,))
    func = cur.fetchone()
    name = func['function_name']
    return render_template('view.html', user=session.get('name'), title=f'View "{name}"', func=func)


@guiapi.route('/delete/<uuid>', methods=['POST'])
#@authenticated
def delete(uuid):
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT function_name, username, functions.deleted FROM functions, users WHERE uuid = %s AND function.user_id = users.id", (uuid,))
        func = cur.fetchone()
        if func['username'] == session.get('username'):
            name = func['function_name']
            if func['deleted'] == False:
                cur.execute("UPDATE functions SET deleted = True WHERE uuid = %s", (uuid,))
                conn.commit()
                flash(f'Deleted Function "{name}".', 'success')
            else:
                flash('There was an issue handling your request.', 'danger')
                return render_template('error.html', user=session.get('name'), title='Page Not Found')
        else:
            return render_template('error.html', user=session.get('name'), title='Forbidden')
    except:
        flash('There was an issue handling your request.', 'danger')
    return redirect(url_for('functions'))


@guiapi.route('/endpoints')
# @authenticated
def endpoints():
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT sites.user_id, endpoint_name, endpoint_uuid, status, sites.created_at FROM sites, users WHERE sites.user_id = users.id AND users.username = %s AND endpoint_name is not null order by created_at desc;", (session.get("username"),))
        endpoints = cur.fetchall()
        endpoints_total = len(endpoints)

        cur.execute(
            "select endpoint_uuid from sites, users where user_id = users.id and username = %s and status='ONLINE' and endpoint_uuid is not null",
            (session.get("username"),))
        endpoints_online_all = cur.fetchall()
        endpoints_online = len(endpoints_online_all)

        cur.execute(
            "select endpoint_uuid from sites, users where user_id = users.id and username = %s and status='OFFLINE' and endpoint_uuid is not null",
            (session.get("username"),))
        endpoints_offline_all = cur.fetchall()
        endpoints_offline = len(endpoints_offline_all)

    except:
        flash('There was an issue handling your request', 'danger')
        return redirect(url_for('guiapi.home'))
    return render_template('endpoints.html', user=session.get('name'), title='Endpoints', endpoints=endpoints, endpoints_total=endpoints_total, endpoints_online=endpoints_online, endpoints_offline=endpoints_offline)
