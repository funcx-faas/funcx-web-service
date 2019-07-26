from flask import (abort, Blueprint, current_app as app, flash, jsonify,
                   redirect, render_template, request, session, url_for)
import uuid
from gui.forms import EditForm
from models.utils import get_db_connection
from authentication.auth import authenticated

# Flask
guiapi = Blueprint("guiapi", __name__)


@guiapi.route('/')
def start():
    return render_template('start.html')


@guiapi.route('/debug')
def debug():
    return jsonify({'username': session.get("username")})


@guiapi.route('/home')
# @authenticated
def home():
    return render_template('home.html', title='Home')


@guiapi.route('/404')
def error():
    return render_template('404.html', title='Error')


@guiapi.route('/functions')
#@authenticated
def functions():
    # functions = Function.query.order_by(Function.date_created).all()
    # length = len(functions)
    # numPages = ceil(length/12)
    return render_template('functions.html', title='Your Functions', functions=functions)


def getUUID():
    return str(uuid.uuid4())


@guiapi.route('/new', methods=['GET', 'POST'])
# @authenticated
def new():

    # TODO (from Tyler) -- have this reroute to funcx.org/api/v1/register_function (rather than reinventing the wheel).
    # TODO: This request should contain: user_id, user_name, short_name
    # TODO: But talk to Ryan about this.

    form = EditForm()
    if form.validate_on_submit():
        name = form.name.data
        desc = form.desc.data
        entry_point = form.entry_point.data
        uuid = getUUID()
        code = form.code.data
        try:
            conn, cur = get_db_connection()
            cur.execute("INSERT INTO functions (function_name, description, entry_point, function_uuid, function_code) VALUES (%s, %s, %s, %s, %s)", (name, desc, entry_point, uuid, code))
            conn.commit()
            flash(f'Saved Function "{name}"!', 'success')
            # return redirect('../view/' + str(450))
            return redirect(url_for('guiapi.home'))
        except:
            flash('There was an issue handling your request', 'danger')
    return render_template('edit.html', title='New Function', form=form, cancel_route="functions")


@guiapi.route('/edit/<id>', methods=['GET', 'POST'])
# @authenticated
def edit(id):
    conn, cur = get_db_connection()
    cur.execute("SELECT * FROM functions WHERE id = %s", (id,))
    func = cur.fetchone()
    name = func['function_name']
    form = EditForm()
    if form.validate_on_submit():
        try:
            # db.session.commit()
            cur.execute("UPDATE functions SET function_name = %s, description = %s, entry_point = %s, modified_at = 'NOW()', function_code = %s WHERE id = %s", (form.name.data, form.desc.data, form.entry_point.data, form.code.data, id))
            conn.commit()
            flash(f'Saved Function "{name}"!', 'success')
            return redirect('../view/' + str(id))
        except:
            flash('There was an issue handling your request.', 'danger')
    form.name.data = func['function_name']
    form.desc.data = func['description']
    form.entry_point.data = func['entry_point']
    # form.language.data = func.language
    form.code.data = func['function_code']
    return render_template('edit.html', title=f'Edit "{form.name.data}"', func=func, form=form, cancel_route="view")


@guiapi.route('/view/<id>')
# @authenticated
def view(id):
    conn, cur = get_db_connection()
    cur.execute("SELECT * FROM functions WHERE id = %s", (id,))
    func = cur.fetchone()
    name = func['function_name']
    return render_template('view.html', title=f'View "{name}"', func=func)


@guiapi.route('/delete/<id>', methods=['GET', 'POST'])
#@authenticated
def delete(id):
    conn, cur = get_db_connection()
    cur.execute("SELECT id, function_name, deleted FROM functions WHERE id = %s", (id,))
    func = cur.fetchone()
    name = func['function_name']
    if func['deleted'] == False:
        try:
            cur.execute("UPDATE functions SET deleted = True WHERE id = %s", (id,))
            conn.commit()
            flash(f'Deleted Function "{name}".', 'success')
        except:
            flash('There was an issue handling your request.', 'danger')
    else:
        flash('There was an issue handling your request.', 'danger')
    # return redirect(url_for('functions'))
    return redirect(url_for('guiapi.home'))