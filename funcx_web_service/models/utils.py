import time
import uuid

import psycopg2
import psycopg2.extras
import redis
from flask import current_app as app

from funcx_web_service.models import search
from funcx_web_service.errors import MissingFunction
from funcx_web_service.models.endpoint import Endpoint
from funcx_web_service.models.function import Function
from funcx_web_service.models.user import User


class db_invocation_logger(object):

    def __init__(self):
        self.conn, self.cur = get_db_connection()

    def log(self, user_id, task_id, function_id, endpoint_id, deferred=False):
        try:
            status = 'CREATED'
            query = "INSERT INTO tasks (user_id, task_id, function_id, endpoint_id, " \
                    "status) values (%s, %s, %s, %s, %s);"
            self.cur.execute(query, (user_id, task_id, function_id, endpoint_id, status))
            if deferred is False:
                self.conn.commit()

        except Exception:
            app.logger.exception("Caught error while writing log update to db")

    def commit(self):
        self.conn.commit()


def add_ep_whitelist(user_name, endpoint_uuid, functions):
    """Add a list of function to the endpoint's whitelist.

    This function is only allowed by the owner of the endpoint.

    Parameters
    ----------
    user_name : str
        The name of the user making the request
    endpoint_uuid : str
        The uuid of the endpoint to add the whitelist entries for
    functions : list
        A list of the function ids to add to the whitelist.

    Returns
    -------
    json
        The result of adding the functions to the whitelist
    """
    saved_user = User.resolve_user(user_name)

    if not saved_user:
        return {'status': 'Failed',
                'reason': f'User {user_name} is not found in database'}

    user_id = saved_user.id

    endpoint = Endpoint.find_by_uuid(endpoint_uuid)

    if not endpoint:
        return {'status': 'Failed',
                'reason': f'Endpoint {endpoint_uuid} is not found in database'}

    if endpoint.user_id != user_id:
        return {'status': 'Failed',
                'reason': f'Endpoint does not belong to User {user_name}'}

    try:
        endpoint.restricted_functions = [
            Function.find_by_uuid(f) for f in functions
        ]
        endpoint.save_to_db()
    except Exception as e:
        print(e)
        return {'status': 'Failed', 'reason': f'Unable to add functions {functions} '
                                              f'to endpoint {endpoint_uuid}, {e}'}

    return {'status': 'Success', 'reason': f'Added functions {functions} '
                                           f'to endpoint {endpoint_uuid} whitelist.'}


def get_ep_whitelist(user_name, endpoint_id):
    """Get the list of functions in an endpoint's whitelist.

    This function is only allowed by the owner of the endpoint.

    Parameters
    ----------
    user_name : str
        The name of the user making the request
    endpoint_id : str
        The uuid of the endpoint to add the whitelist entries for

    Returns
    -------
    json
        The functions in the whitelist
    """
    saved_user = User.resolve_user(user_name)

    if not saved_user:
        return {'status': 'Failed',
                'reason': f'User {user_name} not found in database'}

    user_id = saved_user.id
    conn, cur = get_db_connection()

    # Make sure the user owns the endpoint
    query = "SELECT * from sites where endpoint_uuid = %s and user_id = %s"
    cur.execute(query, (endpoint_id, user_id))
    rows = cur.fetchall()
    functions = []
    try:
        if len(rows) > 0:
            query = "SELECT * from restricted_endpoint_functions where endpoint_id = %s"
            cur.execute(query, (endpoint_id,))
            funcs = cur.fetchall()
            for f in funcs:
                functions.append(f['function_id'])
        else:
            return {'status': 'Failed',
                    'reason': f'User {user_name} is not authorized to perform this action on endpoint {endpoint_id}'}
    except Exception as e:
        return {'status': 'Failed', 'reason': f'Unable to get endpoint {endpoint_id} whitelist, {e}'}

    return {'status': 'Success', 'result': functions}


def delete_ep_whitelist(user_name, endpoint_id, function_id):
    """Delete the functions from an endpoint's whitelist.

    This function is only allowed by the owner of the endpoint.

    Parameters
    ----------
    user_name : str
        The name of the user making the request
    endpoint_id : str
        The uuid of the endpoint to add the whitelist entries for
    function_id : str
        The uuid of the function to remove from the whitelist

    Returns
    -------
    json
        A dict describing the success or failure of removing the function
    """
    saved_user = User.resolve_user(user_name)

    if not saved_user:
        return {'status': 'Failed',
                'reason': f'User {user_name} not found in database'}

    user_id = saved_user.id

    conn, cur = get_db_connection()

    # Make sure the user owns the endpoint
    query = "SELECT * from sites where endpoint_uuid = %s and user_id = %s"
    cur.execute(query, (endpoint_id, user_id))
    rows = cur.fetchall()
    try:
        if len(rows) > 0:
            query = "delete from restricted_endpoint_functions where endpoint_id = %s and function_id = %s"
            cur.execute(query, (endpoint_id, function_id))
            conn.commit()
        else:
            return {'status': 'Failed',
                    'reason': f'User {user_name} is not authorized to perform this action on endpoint {endpoint_id}'}
    except Exception as e:
        return {'status': 'Failed', 'reason': f'Unable to get endpoint {endpoint_id} whitelist, {e}'}

    return {'status': 'Success', 'result': function_id}


def log_invocation(user_id, task_id, function_id, endpoint_id):
    """Insert an invocation into the database.

    Parameters
    ----------
    task : dict
        The dictionary of the task
    """
    try:

        status = 'CREATED'
        conn, cur = get_db_connection()
        query = "INSERT INTO tasks (user_id, task_id, function_id, endpoint_id, " \
                "status) values (%s, %s, %s, %s, %s);"
        cur.execute(query, (user_id, task_id, function_id, endpoint_id, status))

        conn.commit()

    except Exception as e:
        print(e)
        app.logger.error(e)


def ingest_function(function: Function, function_source, user_uuid):
    """Ingest a function into Globus Search

    Restructures data for ingest purposes.

    Parameters
    ----------
    function : Function

    Returns
    -------
    None
    """
    selected_group = None if not function.auth_groups else function.auth_groups[0].group.group_id
    container_uuid = None if not function.container else function.container.container.container_uuid
    data = {
        "function_name": function.function_name,
        "function_code": function.function_source_code,
        "function_source": function_source,
        "container_uuid": container_uuid,
        "entry_point": function.entry_point,
        "description": function.description,
        "public": function.public,
        "group": selected_group
    }
    user_urn = f"urn:globus:auth:identity:{user_uuid}"
    search.func_ingest_or_update(function.function_uuid, data,
                                 author=function.user.username,
                                 author_urn=user_urn)


def ingest_endpoint(user_name, user_uuid, ep_uuid, data):
    owner_urn = f"urn:globus:auth:identity:{user_uuid}"
    search.endpoint_ingest_or_update(ep_uuid, data, owner=user_name, owner_urn=owner_urn)


def register_endpoint(user_name, endpoint_name, description, endpoint_uuid=None):
    """Register the endpoint in the database.

    Parameters
    ----------
    user_name : str
        The primary identity of the user
    endpoint_name : str
        The name of the endpoint
    description : str
        A description of the endpoint
    endpoint_uuid : str
        The uuid of the endpoint (if it exists)

    Returns
    -------
    str
        The uuid of the endpoint
    """
    saved_user = User.resolve_user(user_name)

    if not saved_user:
        return {'status': 'Failed',
                'reason': f'User {user_name} not found in database'}

    user_id = saved_user.id

    if endpoint_uuid:
        # Check it is a valid uuid
        uuid.UUID(endpoint_uuid)

        existing_endpoint = Endpoint.find_by_uuid(endpoint_uuid)

        if existing_endpoint:
            # Make sure user owns this endpoint
            if existing_endpoint.user_id == user_id:
                existing_endpoint.name = endpoint_name
                existing_endpoint.description = description
                existing_endpoint.save_to_db()
                return endpoint_uuid
            else:
                app.logger.debug(f"Endpoint {endpoint_uuid} was previously registered "
                                 f"with user {existing_endpoint.user_id} not {user_id}")
                return None
    try:
        endpoint_uuid = str(uuid.uuid4())
        new_endpoint = Endpoint(user=saved_user,
                                endpoint_name=endpoint_name,
                                description=description,
                                status="OFFLINE",
                                endpoint_uuid=endpoint_uuid
                                )
        new_endpoint.save_to_db()
    except Exception as e:
        app.logger.error(e)
        raise e
    return endpoint_uuid


def resolve_function(user_id, function_uuid):
    """Get the function uuid from database

    Parameters
    ----------
    user_id : str
        The uuid of the user
    function_uuid : str
        The uuid of the function

    Returns
    -------
    str
        The function code
    str
        The function entry point
    str
        The uuid of the container image to use
    """

    start = time.time()
    function_code = None
    function_entry = None
    container_uuid = None

    try:
        conn, cur = get_db_connection()
        query = "select * from functions where function_uuid = %s order by id DESC limit 1"
        cur.execute(query, (function_uuid,))
        r = cur.fetchone()
        if not r:
            raise MissingFunction(function_uuid)

        function_code = r['function_code']
        function_entry = r['entry_point']
        function_id = r['id']
        query = "select * from function_containers, containers, container_images where " \
                "function_containers.function_id = %s and containers.id = function_containers.container_id " \
                "and function_containers.container_id = container_images.container_id " \
                "order by function_containers.id desc limit 1"
        cur.execute(query, (function_id,))
        r = cur.fetchone()

        if r and 'container_uuid' in r:
            container_uuid = r['container_uuid']

    except Exception as e:
        app.logger.exception(e)
        raise
    delta = time.time() - start
    app.logger.info("Time to fetch function {0:.1f}ms".format(delta * 1000))
    return function_code, function_entry, container_uuid


def get_container(container_uuid, container_type):
    """Retrieve the container information.

    Parameters
    ----------
    container_uuid : str
        The container id to look up
    container_type : str
        The container type requested (Docker, Singualrity, Shifter)

    Returns
    -------
    list
        A dictionary describing the container details
    """

    container = {}
    try:
        conn, cur = get_db_connection()
        query = "select * from containers, container_images where containers.id = " \
                "container_images.container_id and container_uuid = %s and type = %s"
        cur.execute(query, (container_uuid, container_type.lower()))
        r = cur.fetchone()
        container['container_uuid'] = r['container_uuid']
        container['name'] = r['name']
        container['type'] = r['type']
        container['location'] = r['location']
    except Exception as e:
        print(e)
        app.logger.error(e)
    return container


def get_db_connection():
    """
    Establish a database connection
    """
    con_str = f"dbname={app.config['DB_NAME']} user={app.config['DB_USER']} password={app.config['DB_PASSWORD']} host={app.config['DB_HOST']}"

    conn = psycopg2.connect(con_str)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    return conn, cur


def get_redis_client():
    """Return a redis client

    Returns
    -------
    redis.StrictRedis
        A client for redis
    """
    try:
        redis_client = redis.StrictRedis(host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT'],
                                         decode_responses=True)
        return redis_client
    except Exception as e:
        print(e)


def update_function(user_name, function_uuid, function_name, function_desc, function_entry_point, function_code):
    """Delete a function

    Parameters
    ----------
    user_name : str
        The primary identity of the user
    function_uuid : str
        The uuid of the function
    function_name : str
        The name of the function
    function_desc : str
        The description of the function
    function_entry_point : str
        The entry point of the function
    function_code : str
        The code of the function

    Returns
    -------
    str
        The result as a status code integer
            "302" for success and redirect
            "403" for unauthorized
            "404" for a non-existent or previously-deleted function
            "500" for try statement error
    """
    try:
        conn, cur = get_db_connection()
        cur.execute(
            "SELECT username, functions.deleted FROM functions, users WHERE function_uuid = %s AND functions.user_id = users.id",
            (function_uuid,))
        func = cur.fetchone()
        if func is not None:
            if not func['deleted']:
                if func['username'] == user_name:
                    cur.execute(
                        "UPDATE functions SET function_name = %s, description = %s, entry_point = %s, modified_at = 'NOW()', function_code = %s WHERE function_uuid = %s",
                        (function_name, function_desc, function_entry_point, function_code, function_uuid))
                    conn.commit()
                    return 302
                else:
                    return 403
            else:
                return 404
        else:
            return 404
    except Exception as e:
        print(e)
        return 500


def delete_function(user_name, function_uuid):
    """Delete a function

    Parameters
    ----------
    user_name : str
        The primary identity of the user
    function_uuid : str
        The uuid of the function

    Returns
    -------
    str
        The result as a status code integer
            "302" for success and redirect
            "403" for unauthorized
            "404" for a non-existent or previously-deleted function
            "500" for try statement error
    """
    try:
        conn, cur = get_db_connection()
        cur.execute(
            "SELECT username, functions.deleted FROM functions, users WHERE function_uuid = %s AND functions.user_id = users.id",
            (function_uuid,))
        func = cur.fetchone()
        if func is not None:
            if not func['deleted']:
                if func['username'] == user_name:
                    cur.execute("UPDATE functions SET deleted = True WHERE function_uuid = %s", (function_uuid,))
                    conn.commit()
                    return 302
                else:
                    return 403
            else:
                return 404
        else:
            return 404
    except Exception as e:
        print(e)
        return 500
