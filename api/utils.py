import numpy as np
import json
import uuid

from config import _load_funcx_client, _get_db_connection
from flask import request, current_app as app


############
# Database #
############
def _create_task(user_id, task_uuid, is_async):
    """
    Insert a task into the database.

    :param input_data:
    :param response:
    :param task_uuid:
    :return:
    """
    start_status = "PENDING"

    try:
        conn, cur = _get_db_connection()
        query = """INSERT INTO tasks (user_id, uuid, status, is_async) values ('{}', '{}', '{}', {});"""\
                .format(user_id, str(task_uuid), start_status, bool(is_async))
        cur.execute(query)
        conn.commit()
    except Exception as e:
        app.logger.error(e)

    res = {"status": start_status, "task_id": str(task_uuid)}
    return res


def _update_task(task_uuid, new_status):
    try:
        conn, cur = _get_db_connection()
        query = """UPDATE tasks SET status = '{}' WHERE task_id = '{}';""".format(new_status, str(task_uuid))
        cur.execute(query)
        conn.commit()

    except Exception as e:
        app.logger.error(e)


def _log_request(user_id, input_data, response_data, endpoint, exec_type):
    """
    Log the invocation time in the database.

    ** NOTE: There is no req_type yet b/c assuming commands.


    :return:
    """

    try:
        conn, cur = _get_db_connection()
        query = """INSERT INTO requests (user_id, endpoint, input_data, response_data) values """ \
                """('{}', '{}', '{}', '{}');"""\
            .format(user_id, endpoint, json.dumps(input_data), json.dumps(response_data))
        cur.execute(query)
        conn.commit()
    except Exception as e:
        app.logger.error(e)


def _decode_result(tmp_res_lst):
    """
    Try to decode the result to make it jsonifiable.

    :param response_list:
    :return: jsonifiable list
    """

    response_list = []
    if isinstance(tmp_res_lst, list):
        for tmp_res in tmp_res_lst:
            if isinstance(tmp_res, np.ndarray):
                response_list.append(tmp_res.tolist())
            else:
                response_list.append(tmp_res)
    elif isinstance(tmp_res_lst, dict):
        response_list = tmp_res_lst
    elif isinstance(tmp_res_lst, np.ndarray):
        response_list.append(tmp_res_lst.tolist())
    return response_list


def _get_zmq_servers():
    """
    Return a dict of ZMQ servers and their ports to route jobs.

    :return: dict, {port:zmqserver}
    """
    conn, cur = _get_db_connection()
    zmq_servers = {}
    try:
        query = "select * from sites where status = 'ONLINE'"
        cur.execute(query)
        rows = cur.fetchall()
        for r in rows:
            port = r['port']
            #wrapper = ZMQWrapper(port)
            #zmq_servers.update({port: wrapper})
    except Exception as e:
        app.logger.error(e)
    return zmq_servers


def _register_function(user_id, function_name, description, function_code, entry_point):
    """
    Register the site in the database.

    :param cur:
    :param conn:
    :param user_id:
    :param endpoint_name:
    :param function_code:
    :param entry_point:
    :return: uuid
    """

    try:
        conn, cur = _get_db_connection()
        function_uuid = str(uuid.uuid4())
        query = """INSERT INTO functions (user_id, name, description, status, function_name, function_uuid, function_code, entry_point) values """ \
                """('{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}');"""\
            .format(user_id, '', description, 'REGISTERED', function_name, function_uuid, function_code, entry_point)
        cur.execute(query)
        conn.commit()
    except Exception as e:
        app.logger.error(e)
    return function_uuid

def _register_site(user_id, endpoint_name, description):
    """
    Register the site in the database.

    :param cur:
    :param conn:
    :param user_id:
    :param endpoint_name:
    :param description:
    :return: uuid
    """

    try:
        conn, cur = _get_db_connection()
        endpoint_uuid = _resolve_endpoint(user_id, endpoint_name)
        if endpoint_uuid:
            return endpoint_uuid
        endpoint_uuid = str(uuid.uuid4())
        query = """INSERT INTO sites (user_id, name, description, status, endpoint_name, endpoint_uuid) values """ \
                """('{}', '{}', '{}', '{}', '{}', '{}');"""\
            .format(user_id, '', description, 'OFFLINE', endpoint_name, endpoint_uuid)
        cur.execute(query)
        conn.commit()
    except Exception as e:
        app.logger.error(e)
    return endpoint_uuid


def _resolve_endpoint(user_id, endpoint_name, status=None):
    """
    Get the endpoint uuid from database
    """

    endpoint_uuid = None
    try:
        conn, cur = _get_db_connection() 
        query = "select * from sites where endpoint_name = '{}' and user_id = {} order by id DESC limit 1".format(endpoint_name, user_id)
        if status:
            query = "select * from sites where status = '{}' and endpoint_name = '{}' and user_id = {} order by id DESC limit 1".format(status, endpoint_name, user_id)
        # print(query)
        cur.execute(query)
        r = cur.fetchone()
        endpoint_uuid = r['endpoint_uuid']
    except Exception as e:
        app.logger.error(e)
    return endpoint_uuid


def _resolve_function(user_id, function_name):
    """
    Get the function uuid from database
    """

    function_code = None
    function_entry = None
    try:
        conn, cur = _get_db_connection()
        query = "select * from functions where function_name = '{}' and user_id = {} order by id DESC limit 1".format(function_name, user_id)
        cur.execute(query)
        r = cur.fetchone()
        function_code = r['function_code']
        function_entry = r['entry_point']

    except Exception as e:
        app.logger.error(e)
    return (function_code, function_entry)


########
# Auth #
########

def _introspect_token(headers):
    """
    Decode the token and retrieve the user's details

    :param headers:
    :return:
    """
    user_name = None
    if 'Authorization' in headers:
        token = request.headers.get('Authorization')
        app.logger.debug(token)
        token = token.split(" ")[1]
        try:
            client = _load_funcx_client()
            auth_detail = client.oauth2_token_introspect(token)
            app.logger.debug(auth_detail)
            user_name = auth_detail['username']
        except Exception as e:
            app.logger.error('Auth error:', e)
    return user_name


def _get_user(headers):
    """
    Get the user details from the database.

    :param headers:
    :return:
    """

    user_name = _introspect_token(headers)
    short_name = None
    user_id = None

    app.logger.debug('Authorizing user: {}'.format(user_name))
    if not user_name:
        return None, None, None

    # Now check if it is in the database.
    try:
        conn, cur = _get_db_connection()
        cur.execute("""SELECT * from users where username = '{}'""".format(user_name))
        rows = cur.fetchall()
        if len(rows) > 0:
            for r in rows:
                short_name = r['namespace']
                user_id = r['id']
        else:
            short_name = "{name}_{org}".format(name=user_name.split("@")[0], org=user_name.split("@")[1].split(".")[0])
            cmd = """INSERT into users (username, globus_identity, namespace) values """\
                  """('{name}', '{globus}', '{short}') RETURNING id"""\
                .format(name=user_name, globus=user_name, short=short_name)
            cur.execute(cmd)
            conn.commit()
            user_id = cur.fetchone()[0]
    except Exception as e:
        app.logger.error(e)
    return user_id, user_name, short_name

