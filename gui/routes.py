from flask import (abort, Blueprint, current_app as app, flash, jsonify,
                   redirect, render_template, request, session, url_for)
import time
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
    try:
        conn, cur = get_db_connection()
        cur.execute(
            "SELECT tasks.created_at, tasks.modified_at FROM tasks;")
        all_tasks = cur.fetchall()
        times = list()
        for task in all_tasks:
            times.append(task['modified_at'] - task['created_at'])
        count = timedelta(hours=0)
        for time in times:
            count += time
        total_CPU = num_delimiter(round((count.total_seconds() / 3600.0), 2), "decimal")
    except:
        flash('There was an issue handling your request.', 'danger')
    return render_template('start.html', title='Start', total_CPU=total_CPU)


def num_delimiter(num, type):
    num = str(num)
    decimal = len(num)
    if type == "decimal":
        decimal = None
        for i in num:
            if i == ".":
                decimal = num.index(i)
                break
        if decimal == None:
            num = num + ".00"
            decimal = num.index(".")
        while num[-3] != ".":
            num = num + "0"
    i = decimal - 3
    while i > 0:
        num = num[:i] + "," + num[i:]
        i -= 3
    return num


# @guiapi.route('/debug')
# def debug():
#     session.update(
#         username='ryan@globusid.org',
#         name='Ryan Chard'
#         # username='aschwartz417@uchicago.edu',
#         # name='Avery Schwartz'
#         # username='t-9lee3@uchicago.edu',
#         # name='Teresa Lee'
#         # username='skluzacek@uchicago.edu',
#         # name='Tyler Skluzacek'
#     )
#     return jsonify({'username': session.get("username")})


@guiapi.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('auth_api.login'))
    stats = [0 for i in range(3)]
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT count(functions.id) FROM functions, users WHERE functions.user_id = users.id AND users.username = %s", (session.get("username"),))
        executions = cur.fetchone()
        stats[0] = num_delimiter(executions['count'], "int")

        cur.execute(
            "SELECT tasks.created_at, tasks.modified_at FROM tasks, users WHERE cast(tasks.user_id as integer) = users.id AND users.username = %s",
            (session.get("username"),))
        tasks = cur.fetchall()
        stats[1] = num_delimiter(len(tasks), "int")
        if len(tasks) != 0:
            times = list()
            for task in tasks:
                times.append(task['modified_at'] - task['created_at'])
            count = timedelta(hours=0)
            for time in times:
                count += time
            stats[2] = num_delimiter(round((count.total_seconds() / 3600.0), 2), "decimal")
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.start'))
    return render_template('home.html', user=session.get('name'), title='Home', stats=stats)


# @guiapi.route('/about')
# def about():
#     return render_template('about.html', user=session.get('name'), title='About')

@guiapi.route('/functions')
def functions():
    if 'username' not in session:
        return redirect(url_for('auth_api.login'))
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
def function_new():
    if 'username' not in session:
        return redirect(url_for('auth_api.login'))
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
def function_edit(uuid):
    if 'username' not in session:
        return redirect(url_for('auth_api.login'))
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT function_name, description, entry_point, username, timestamp, modified_at, function_uuid, status, function_code FROM functions, users WHERE function_uuid = %s AND functions.user_id = users.id", (uuid,))
        func = cur.fetchone()
        if func == None:
            return render_template('error.html', user=session.get('name'), title='404 Not Found')
        if func['username'] != session.get('username'):
            return render_template('error.html', user=session.get('name'), title='403 Forbidden')
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.function_view', uuid=uuid))
    name = func['function_name']

    form = EditForm()
    if form.validate_on_submit():
        json = {'func': func['function_uuid'], 'name': form.name.data, 'desc': form.desc.data, 'entry_point': form.entry_point.data, 'code': form.code.data}
        tokens = session.get("tokens")
        funcx_tokens = tokens['funcx_service']
        access_token = "Bearer " + funcx_tokens['access_token']
        response = requests.post("http://dev.funcx.org/api/v1/upd_function", headers={"Authorization": access_token}, json=json)
        result = response.json()['result']
        if result == 302:
            flash(f'Saved Function "{form.name.data}"!', 'success')
            return redirect(url_for('guiapi.function_view', uuid=uuid))
        elif result == 403:
            return render_template('error.html', user=session.get('name'), title='403 Forbidden')
        elif result == 404:
            return render_template('error.html', user=session.get('name'), title='404 Not Found')
        else:
            flash('There was an issue handling your request.', 'danger')
            # return redirect(url_for('guiapi.function_view', uuid=uuid))

    form.name.data = func['function_name']
    form.desc.data = func['description']
    form.entry_point.data = func['entry_point']
    form.code.data = func['function_code']
    return render_template('function_edit.html', user=session.get('name'), title=f'Edit "{name}"', func=func, form=form, cancel_route="view")


@guiapi.route('/function/<uuid>/view', methods=['GET', 'POST'])
def function_view(uuid):
    if 'username' not in session:
        return redirect(url_for('auth_api.login'))
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT function_name, description, entry_point, users.id, username, timestamp, modified_at, function_uuid, status, function_code FROM functions, users WHERE function_uuid = %s AND functions.user_id = users.id AND functions.deleted = False", (uuid,))
        func = cur.fetchone()
        if func == None:
            return render_template('error.html', user=session.get('name'), title='404 Not Found')
        if func['username'] != session.get('username'):
            return render_template('error.html', user=session.get('name'), title='403 Forbidden')
        name = func['function_name']
        user_id = func['id']
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.functions'))

    execute_form = ExecuteForm()
    cur.execute("SELECT DISTINCT endpoint_name, endpoint_uuid FROM sites WHERE endpoint_uuid IS NOT NULL AND ((user_id = %s AND sites.public = false) OR (sites.public = true));",
                (user_id,))
    endpoints = cur.fetchall()
    endpoint_uuids = list()
    for endpoint in endpoints:
        endpoint_uuids.append((endpoint['endpoint_uuid'], endpoint['endpoint_name']))
    execute_form.endpoint.choices = endpoint_uuids
    if execute_form.validate_on_submit() and execute_form.submit.data:
        json = {'func': func['function_uuid'], 'endpoint': execute_form.endpoint.data, 'data': execute_form.data.data}
        # tokens = session.get("tokens")
        # funcx_tokens = tokens['funcx_service']
        # access_token = "Bearer " + funcx_tokens['access_token']
        print("Sending Request")
        response = requests.post("http://funcx.org/api/v1/execute", headers={"Authorization": access_token}, json=json)
        task_id = response.json()['task_id']
        time.sleep(1)
        return redirect(url_for('guiapi.task_view', task_id=task_id))
    else:
        print(execute_form.validate_on_submit())
        print(execute_form.submit.data)
        print("nope")

    delete_form = DeleteForm()
    if delete_form.validate_on_submit() and delete_form.delete.data:
        print("Delete:" + str(delete_form.validate_on_submit()))
        print("Delete:" + str(delete_form.delete.data))
        json = {'func': func['function_uuid']}
        tokens = session.get("tokens")
        funcx_tokens = tokens['funcx_service']
        access_token = "Bearer " + funcx_tokens['access_token']
        response = requests.post("http://dev.funcx.org/api/v1/delete_function", headers={"Authorization": access_token}, json=json)
        result = response.json()['result']
        if result == 302:
            flash(f'Deleted Function "{name}".', 'success')
            return redirect(url_for('guiapi.functions'))
        elif result == 403:
            return render_template('error.html', user=session.get('name'), title='403 Forbidden')
        elif result == 404:
            return render_template('error.html', user=session.get('name'), title='404 Not Found')
        else:
            flash('There was an issue handling your request.', 'danger')
            # return redirect(url_for('guiapi.functions'))

    return render_template('function_view.html', user=session.get('name'), title=f'View "{name}"', func=func, execute_form=execute_form, delete_form=delete_form)


@guiapi.route('/endpoints')
def endpoints():
    if 'username' not in session:
        return redirect(url_for('auth_api.login'))
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT DISTINCT sites.user_id, endpoint_name, endpoint_uuid, status, sites.created_at, public FROM sites, users WHERE ((sites.user_id = users.id AND users.username = %s AND sites.public = 'f') OR (sites.public = 't')) AND sites.deleted = 'f' AND endpoint_uuid is not null order by created_at desc;", (session.get("username"),))
        endpoints = cur.fetchall()
        endpoints_total = len(endpoints)
        private_endpoints = list()
        private_endpoints_total = 0
        private_endpoints_online_total = 0
        public_endpoints = list()
        public_endpoints_total = 0
        public_endpoints_online_total = 0
        for endpoint in endpoints:
            if endpoint['public'] is False:
                private_endpoints_total += 1
                if endpoint['status'] == "ONLINE":
                    private_endpoints_online_total += 1
            else:
                public_endpoints_total += 1
                if endpoint['status'] == "ONLINE":
                    public_endpoints_online_total += 1
        private_endpoints.append(private_endpoints_total)
        private_endpoints.append(private_endpoints_online_total)
        private_endpoints.append(private_endpoints_total - private_endpoints_online_total)
        public_endpoints.append(public_endpoints_total)
        public_endpoints.append(public_endpoints_online_total)
        public_endpoints.append(public_endpoints_total - public_endpoints_online_total)

        numPages = ceil(endpoints_total / 30)
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.home'))
    return render_template('endpoints.html', user=session.get('name'), title='Endpoints', endpoints=endpoints, endpoints_total=endpoints_total, private_endpoints=private_endpoints, public_endpoints=public_endpoints, numPages=numPages)


@guiapi.route('/endpoint/<endpoint_uuid>/view', methods=['GET', 'POST'])
def endpoint_view(endpoint_uuid):
    if 'username' not in session:
        return redirect(url_for('auth_api.login'))
    try:
        conn, cur = get_db_connection()
        cur.execute(
            "SELECT sites.id, sites.user_id, sites.created_at, status, endpoint_name, endpoint_uuid, public, sites.deleted, username "
            "FROM sites, users "
            "WHERE sites.endpoint_uuid = %s "
            "AND users.id = sites.user_id "
            "AND endpoint_name IS NOT NULL AND sites.deleted = 'f';",
            (endpoint_uuid,))
        endpoint = cur.fetchone()
        if endpoint == None:
            return render_template('error.html', user=session.get('name'), title='404 Not Found')
        if endpoint['username'] != session.get('username') and endpoint['public'] is False:
            return render_template('error.html', user=session.get('name'), title='403 Forbidden')
        name = endpoint['endpoint_name']
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.endpoints'))

    delete_form = DeleteForm()
    if delete_form.validate_on_submit() and delete_form.delete.data:
        json = {'endpoint': endpoint['endpoint_uuid']}
        tokens = session.get("tokens")
        funcx_tokens = tokens['funcx_service']
        access_token = "Bearer " + funcx_tokens['access_token']
        response = requests.post("http://dev.funcx.org/api/v1/delete_endpoint", headers={"Authorization": access_token},
                                 json=json)
        result = response.json()['result']
        if result == 302:
            flash(f'Deleted Endpoint "{name}".', 'success')
            return redirect(url_for('guiapi.endpoints'))
        elif result == 403:
            return render_template('error.html', user=session.get('name'), title='403 Forbidden')
        elif result == 404:
            return render_template('error.html', user=session.get('name'), title='404 Not Found')
        else:
            flash('There was an issue handling your request.', 'danger')
            # return redirect(url_for('guiapi.endpoints'))

    return render_template('endpoint_view.html', user=session.get('name'), title=f'View "{name}"', endpoint=endpoint, delete_form=delete_form)



@guiapi.route('/tasks')
def tasks():
    if 'username' not in session:
        return redirect(url_for('auth_api.login'))
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT tasks.id, users.id, cast(tasks.user_id as integer), tasks.task_id, results.result, tasks.status, tasks.function_id, functions.function_name, tasks.endpoint_id, sites.endpoint_name "
                    "FROM results, tasks, users, functions, sites "
                    "WHERE results.task_id = tasks.task_id AND users.id = cast(tasks.user_id as integer) AND sites.endpoint_uuid = tasks.endpoint_id AND functions.function_uuid = tasks.function_id "
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
def task_view(task_id):
    if 'username' not in session:
        return redirect(url_for('auth_api.login'))
    try:
        conn, cur = get_db_connection()
        cur.execute(
            "SELECT tasks.id, tasks.user_id, tasks.task_id, tasks.status, results.result, tasks.created_at, tasks.modified_at, tasks.function_id, functions.function_name, tasks.endpoint_id, sites.endpoint_name, username "
            "FROM tasks, results, sites, functions, users "
            "WHERE results.task_id = tasks.task_id AND sites.endpoint_uuid = tasks.endpoint_id AND functions.function_uuid = tasks.function_id AND tasks.task_id = %s AND cast(tasks.user_id as integer) = users.id "
            "AND function_id IS NOT NULL;",
            (task_id,))
        task = cur.fetchone()
        if task == None:
            return render_template('error.html', user=session.get('name'), title='404 Not Found')
        if task['username'] != session.get('username'):
            return render_template('error.html', user=session.get('name'), title='403 Forbidden')
        name = task['task_id']
    except:
        flash('There was an issue handling your request.', 'danger')
        return redirect(url_for('guiapi.tasks'))
    return render_template('task_view.html', user=session.get('name'), title='View Task', task=task)


@guiapi.route('/function/<uuid>/tasks')
def function_tasks(uuid):
    if 'username' not in session:
        return redirect(url_for('auth_api.login'))
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT function_uuid, function_name, username FROM functions, users WHERE function_uuid = %s AND functions.user_id = users.id", (uuid,))
        func = cur.fetchone()
        if func == None:
            return render_template('error.html', user=session.get('name'), title='404 Not Found')
        if func['username'] != session.get('username'):
            return render_template('error.html', user=session.get('name'), title='403 Forbidden')
        func_name = func['function_name']
        cur.execute(
            "SELECT task_id, cast(tasks.user_id as integer), tasks.function_id, functions.function_name, tasks.status, tasks.created_at, tasks.endpoint_id, sites.endpoint_name "
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
