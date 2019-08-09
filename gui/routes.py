from flask import (abort, Blueprint, current_app as app, flash, jsonify,
                   redirect, render_template, request, session, url_for)
import requests
import uuid
from math import *
from datetime import datetime, timedelta
from gui.forms import EditForm, ExecuteForm, DeleteForm
from models.utils import get_db_connection, register_function
from authentication.auth import authenticated

# Flask
guiapi = Blueprint("guiapi", __name__)


@guiapi.route('/')
def start():
    return render_template('start.html', title='Start')


@guiapi.route('/debug')
def debug():
    session.update(
        # username='ryan@globusid.org',
        # name='Ryan Chard'
        # username='aschwartz417@uchicago.edu',
        # name='Avery Schwartz'
        # username='t-9lee3@uchicago.edu',
        # name='Teresa Lee'
        # username='skluzacek@uchicago.edu',
        # name='Tyler Skluzacek'
    )
    return jsonify({'username': session.get("username")})


@guiapi.route('/home')
# @authenticated
def home():
    stats = [0 for i in range(3)]
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT count(functions.id) FROM functions, users WHERE functions.user_id = users.id AND users.username = %s", (session.get("username"),))
        executions = cur.fetchone()
        stats[0] = executions['count']

        cur.execute(
            "SELECT tasks.created_at, tasks.modified_at FROM tasks, users WHERE cast(tasks.user_id as integer) = users.id AND users.username = %s",
            (session.get("username"),))
        tasks = cur.fetchall()
        stats[1] = len(tasks)
        if len(tasks) != 0:
            times = list()
            for task in tasks:
                times.append(task['modified_at'] - task['created_at'])
            count = timedelta(hours=0)
            for time in times:
                count += time
            stats[2] = round((count.total_seconds() / 3600.0), 2)
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.start'))
    return render_template('home.html', user=session.get('name'), title='Home', stats=stats, token=session.get("tokens"))


@guiapi.route('/error')
# @authenticated
def error():
    return render_template('error.html', user=session.get('name'), title='404 Page Not Found')



@guiapi.route('/functions')
# @authenticated
def functions():
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT function_name, timestamp, modified_at, function_uuid FROM functions, users WHERE functions.user_id = users.id AND users.username = %s AND functions.deleted = False ORDER BY functions.id desc", (session.get("username"),))
        functions = cur.fetchall()
        functions_total = len(functions)
        numPages = ceil(functions_total / 30)
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.home'))
    return render_template('functions.html', user=session.get('name'), title='Your Functions', functions=functions, functions_total=functions_total, numPages=numPages)


def getUUID():
    return str(uuid.uuid4())


@guiapi.route('/function/new', methods=['GET', 'POST'])
# @authenticated
def function_new():
    form = EditForm()
    if form.validate_on_submit():
        name = form.name.data
        try:
            uuid = register_function(session.get('username'), name, form.desc.data, form.code.data, form.entry_point.data, None)
            flash(f'Saved Function "{name}"!', 'success')
            return redirect(url_for('guiapi.function_view', uuid=uuid))
        except:
            flash('There was an issue handling your request.', 'danger')
    return render_template('function_edit.html', user=session.get('name'), title='New Function', form=form, cancel_route="functions")


@guiapi.route('/function/<uuid>/edit', methods=['GET', 'POST'])
# @authenticated
def function_edit(uuid):
    conn, cur = get_db_connection()
    cur.execute("SELECT function_name, description, entry_point, username, timestamp, modified_at, function_uuid, status, function_code FROM functions, users WHERE function_uuid = %s AND functions.user_id = users.id", (uuid,))
    func = cur.fetchone()
    if func == None:
        return render_template('error.html', user=session.get('name'), title='404 Page Not Found')
    name = func['function_name']
    form = EditForm()
    if form.validate_on_submit():
        try:
            cur.execute("UPDATE functions SET function_name = %s, description = %s, entry_point = %s, modified_at = 'NOW()', function_code = %s WHERE function_uuid = %s", (form.name.data, form.desc.data, form.entry_point.data, form.code.data, uuid))
            conn.commit()
            flash(f'Saved Function "{form.name.data}"!', 'success')
            return redirect(url_for('guiapi.function_view', uuid=uuid))
        except:
            flash('There was an issue handling your request.', 'danger')
    form.name.data = func['function_name']
    form.desc.data = func['description']
    form.entry_point.data = func['entry_point']
    form.code.data = func['function_code']
    return render_template('function_edit.html', user=session.get('name'), title=f'Edit "{form.name.data}"', func=func, form=form, cancel_route="view")


@guiapi.route('/function/<uuid>/view', methods=['GET', 'POST'])
# @authenticated
def function_view(uuid):
    conn, cur = get_db_connection()
    cur.execute("SELECT function_name, description, entry_point, users.id, username, timestamp, modified_at, function_uuid, status, function_code FROM functions, users WHERE function_uuid = %s AND functions.user_id = users.id AND functions.deleted = False", (uuid,))
    func = cur.fetchone()
    if func == None:
        return render_template('error.html', user=session.get('name'), title='404 Page Not Found')
    name = func['function_name']
    user_id = func['id']

    form = ExecuteForm()
    form.func.data = func['function_uuid']
    cur.execute("SELECT endpoint_name, endpoint_uuid FROM sites WHERE endpoint_uuid IS NOT NULL AND user_id = %s;",
                (user_id,))
    endpoints = cur.fetchall()
    endpoint_uuids = list()
    for endpoint in endpoints:
        endpoint_uuids.append((endpoint['endpoint_uuid'], endpoint['endpoint_name']))  # Second Field is display name
    endpoint_uuids.append(("a92945a1-2778-4417-8cd1-4957bc35ce66", "dlhub-endpoint-deployment-6bb559f4f-v7g77"))
    form.endpoint.choices = endpoint_uuids

    if form.validate_on_submit() and form.submit.data:
        print("Run: " + str(form.submit.data))
        json = {'func': form.func.data, 'endpoint': form.endpoint.data, 'data': form.data.data}
        print(json)
        print(type(json))
        tokens = session.get("tokens")
        funcx_tokens = tokens['funcx_service']
        access_token = "Bearer " + funcx_tokens['access_token']
        response = requests.post("http://funcx.org/api/v1/execute", headers={"Authorization": access_token}, json=json)
        task_id = response.json['task_id']
        print(task_id)
        redirect(url_for('guiapi.task_view', task_id=task_id))

    delete_form = DeleteForm()
    if form.validate_on_submit() and delete_form.delete.data:
        print("Delete: " + str(delete_form.delete.data))
        # return redirect(url_for('guiapi.function_delete', uuid=func['function_uuid']))
        # function_delete(func['function_uuid'])
        return redirect(url_for('guiapi.functions'))

    return render_template('function_view.html', user=session.get('name'), title=f'View "{name}"', func=func, form=form, delete_form=delete_form)


# @guiapi.route('/function/<uuid>/delete', methods=['POST'])
#@authenticated
def function_delete(uuid):
    # try:
        conn, cur = get_db_connection()
        cur.execute("SELECT function_name, username, functions.deleted FROM functions, users WHERE function_uuid = %s AND functions.user_id = users.id", (uuid,))
        func = cur.fetchone()
        if func['username'] == session.get('username'):
            name = func['function_name']
            if func['deleted'] == False:
                cur.execute("UPDATE functions SET deleted = True WHERE function_uuid = %s", (uuid,))
                conn.commit()
        #         flash(f'Deleted Function "{name}".', 'success')
        #     else:
        #         flash('There was an issue handling your request.', 'danger')
        #         return render_template('error.html', user=session.get('name'), title='404 Page Not Found')
        # else:
        #     return render_template('error.html', user=session.get('name'), title='403 Forbidden')
    # except:
    #     print("except")
    #     flash('There was an issue handling your request.', 'danger')
    # return redirect(url_for('functions'))


@guiapi.route('/endpoints')
# @authenticated
def endpoints():
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT sites.user_id, endpoint_name, endpoint_uuid, status, sites.created_at FROM sites, users WHERE sites.user_id = users.id AND users.username = %s AND sites.deleted = 'f' AND endpoint_name is not null order by created_at desc;", (session.get("username"),))
        endpoints = cur.fetchall()
        endpoints_total = len(endpoints)

        cur.execute(
            "select endpoint_uuid from sites, users where user_id = users.id and username = %s and status='ONLINE' AND sites.deleted = 'f' and endpoint_uuid is not null",
            (session.get("username"),))
        endpoints_online_all = cur.fetchall()
        endpoints_online = len(endpoints_online_all)

        cur.execute(
            "select endpoint_uuid from sites, users where user_id = users.id and username = %s and status='OFFLINE' AND sites.deleted = 'f' and endpoint_uuid is not null",
            (session.get("username"),))
        endpoints_offline_all = cur.fetchall()
        endpoints_offline = len(endpoints_offline_all)

        numPages = ceil(endpoints_total / 30)
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.home'))
    return render_template('endpoints.html', user=session.get('name'), title='Endpoints', endpoints=endpoints, endpoints_total=endpoints_total, endpoints_online=endpoints_online, endpoints_offline=endpoints_offline, numPages=numPages)


@guiapi.route('/tasks')
# @authenticated
def tasks():
    try:
        conn, cur = get_db_connection()

        cur.execute("SELECT tasks.id, users.id, cast(tasks.user_id as integer), tasks.task_id, results.result, tasks.status, tasks.function_id, functions.function_name, tasks.endpoint_id, sites.endpoint_name "
                    "FROM results, tasks, users, functions, sites "
                    "WHERE results.task_id = tasks.task_id AND users.id = cast(tasks.user_id as integer) AND sites.endpoint_uuid = tasks.endpoint_id AND functions.function_uuid = tasks.function_id  "
                    "AND function_id IS NOT NULL AND users.username = %s "
                    "ORDER by tasks.id desc",
                    (session.get("username"),))
        tasks = cur.fetchall()

        tasks_total = len(tasks)
        numPages = ceil(tasks_total / 30)
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.home'))
    return render_template('tasks.html', user=session.get('name'), title='Tasks', tasks=tasks, tasks_total=tasks_total, numPages=numPages)


@guiapi.route('/task/<task_id>/view')
# @authenticated
def task_view(task_id):

    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT tasks.id, tasks.user_id, tasks.task_id, tasks.status, results.result, tasks.created_at, tasks.modified_at, tasks.function_id, functions.function_name, tasks.endpoint_id, sites.endpoint_name "
                    "FROM tasks, results, sites, functions "
                    "WHERE results.task_id = tasks.task_id AND sites.endpoint_uuid = tasks.endpoint_id AND functions.function_uuid = tasks.function_id AND tasks.task_id = %s "
                    "AND function_id IS NOT NULL;",
                    (task_id,))
        task = cur.fetchone()
        if task == None:
            return render_template('error.html', user=session.get('name'), title='404 Page Not Found')
        name = task['task_id']
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.tasks'))
    return render_template('task_view.html', user=session.get('name'), title='View Task', task=task)


@guiapi.route('/function/<uuid>/tasks')
#@authenticated
def function_tasks(uuid):
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT function_uuid, function_name FROM functions WHERE function_uuid = %s", (uuid,))
        func = cur.fetchone()
        if func == None:
            return render_template('error.html', user=session.get('name'), title='404 Page Not Found')
        func_name = func['function_name']
        cur.execute(
            "SELECT tasks.task_id, cast(tasks.user_id as integer), tasks.function_id, functions.function_name, tasks.status, tasks.created_at, tasks.endpoint_id, sites.endpoint_name "
            "FROM tasks, sites, users, functions "
            "WHERE tasks.endpoint_id = sites.endpoint_uuid AND cast(tasks.user_id as integer) = users.id AND tasks.function_id = functions.function_uuid "
            "AND tasks.function_id = %s"
            "ORDER by tasks.task_id desc", (uuid,))
        func_tasks = cur.fetchall()
        tasks_total = len(func_tasks)
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.function_view', func=func))

    try:
        numPages = ceil(tasks_total / 30)
    except:
        return render_template('function_tasks.html', user=session.get('name'), title=f'Tasks of "{func_name}"')
    return render_template('function_tasks.html', user=session.get('name'), title=f'Tasks of "{func_name}"', func_tasks=func_tasks, tasks_total=tasks_total, func=func, numPages=numPages)


