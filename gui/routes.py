from flask import (abort, Blueprint, current_app as app, flash, jsonify,
                   redirect, render_template, request, session, url_for)

import uuid
from gui.forms import EditForm
from models.utils import get_db_connection

# Flask
guiapi = Blueprint("guiapi", __name__)

conn, cur = get_db_connection()

@guiapi.route('/')
def start():
    return render_template('start.html')

@guiapi.route('/home')
def home():
    return render_template('home.html', title='Home')

@guiapi.route('/functions')
def functions():
    # functions = Function.query.order_by(Function.date_created).all()
    # length = len(functions)
    # numPages = ceil(length/12)
    return render_template('functions.html', title='Your Functions', functions=functions)

def getUUID():
    return str(uuid.uuid4())

@guiapi.route('/new', methods=['GET', 'POST'])
def new():
    form = EditForm()
    if form.validate_on_submit():
        name = form.title.data
        uuid = getUUID()
        code = form.content.data
        try:
            cur.execute("INSERT INTO functions (function_name, function_uuid, function_code) VALUES (%s, %s, %s)", (name, uuid, code))
            conn.commit()
            flash(f'Saved Function "{name}"!', 'success')
            # return redirect('../view/' + str(450))
            return redirect(url_for('guiapi.home'))
        except:
            flash('There was an issue handling your request', 'danger')
    return render_template('edit.html', title='New Function', form=form, cancel_route="functions")

@guiapi.route('/edit/<id>', methods=['GET', 'POST'])
def edit(id):
    cur.execute("SELECT * FROM functions WHERE id = %s", (id,))
    func = cur.fetchone()
    name = func['function_name']
    form = EditForm()
    if form.validate_on_submit():
        name = form.title.data
        # func.language = form.language.data
        code = form.content.data
        try:
            # db.session.commit()
            cur.execute("UPDATE functions SET function_name = %s, function_code = %s, modified_at = 'NOW()' WHERE id = %s", (name, code, id))
            conn.commit()
            flash(f'Saved Function "{name}"!', 'success')
            return redirect('../view/' + str(id))
        except:
            flash('There was an issue handling your request.', 'danger')
    form.title.data = func['function_name']
    # form.language.data = func.language
    form.content.data = func['function_code']
    return render_template('edit.html', title=f'Edit "{name}"', func=func, form=form, cancel_route="view")


@guiapi.route('/view/<id>')
def view(id):
    cur.execute("SELECT id, function_name, user_id, description, timestamp, modified_at, function_uuid, function_code FROM functions WHERE id = %s", (id,))
    func = cur.fetchone()
    name = func['function_name']
    user_id = func['user_id']
    desc = func['description']
    date_created = func['timestamp']
    date_modified = func['modified_at']
    function_uuid = func['function_uuid']
    function_code = func['function_code']
    return render_template('view.html', title=f'View "{name}"', id=id, name=name, user_id=user_id, desc=desc, date_created=date_created, date_modified=date_modified, function_uuid=function_uuid, function_code=function_code)

@guiapi.route('/delete/<id>', methods=['GET', 'POST'])
def delete(id):
    cur.execute("SELECT id, function_name, deleted FROM functions WHERE id = %s", (id,))
    func = cur.fetchone()
    name = func['function_name']
    # print(str(routed))
    if(func['deleted'] == False):
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