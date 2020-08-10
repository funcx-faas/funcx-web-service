import time
import uuid

import psycopg2
import psycopg2.extras
import redis
from flask import current_app as app

from funcx_web_service import models
from funcx_web_service.errors import UserNotFound, MissingFunction


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


def add_ep_whitelist(user_name, endpoint_id, functions):
    """Add a list of function to the endpoint's whitelist.

    This function is only allowed by the owner of the endpoint.

    Parameters
    ----------
    user_name : str
        The name of the user making the request
    endpoint_id : str
        The uuid of the endpoint to add the whitelist entries for
    functions : list
        A list of the function ids to add to the whitelist.

    Returns
    -------
    json
        The result of adding the functions to the whitelist
    """
    user_id = resolve_user(user_name)

    conn, cur = get_db_connection()

    # Make sure the user owns the endpoint
    query = "SELECT * from sites where endpoint_uuid = %s and user_id = %s"
    cur.execute(query, (endpoint_id, user_id))
    rows = cur.fetchall()
    try:
        if len(rows) > 0:
            for function_id in functions:
                query = "INSERT INTO restricted_endpoint_functions (endpoint_id, function_id) values (%s, %s)"
                cur.execute(query, (endpoint_id, function_id))
            conn.commit()
        else:
            return {'status': 'Failed',
                    'reason': f'User {user_name} is not authorized to perform this action on endpoint {endpoint_id}'}
    except Exception as e:
        return {'status': 'Failed', 'reason': f'Unable to add functions {functions} to endpoint {endpoint_id}, {e}'}

    return {'status': 'Success', 'reason': f'Added functions {functions} to endpoint {endpoint_id} whitelist.'}


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
    user_id = resolve_user(user_name)

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
    user_id = resolve_user(user_name)

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


def register_function(user_name, function_name, description, function_code, entry_point, container_uuid, group, public):
    """Register the site in the database.

    Parameters
    ----------
    user_name : str
        The primary identity of the user
    function_name : str
        The name of the function
    description : str
        A description of the function
    function_code : str
        The function's code
    entry_point : str
        The entry point to the function (function name)
    container_uuid : str
        The uuid of the container to map this to
    group : str
        A globus group id to share the function with
    public : bool
        Whether or not the function is publicly available

    Returns
    -------
    str
        The uuid of the function
    """
    user_id = resolve_user(user_name)

    conn, cur = get_db_connection()
    function_uuid = str(uuid.uuid4())
    query = "INSERT INTO functions (user_id, name, description, status, function_name, function_uuid, " \
            "function_code, entry_point, public) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
    cur.execute(query, (user_id, '', description, 'REGISTERED', function_name,
                        function_uuid, function_code, entry_point, public))

    if container_uuid is not None:
        app.logger.debug(f'Inserting container mapping: {container_uuid}')
        query = "INSERT INTO function_containers (container_id, function_id) values (" \
                "(SELECT id from containers where container_uuid = %s), " \
                "(SELECT id from functions where function_uuid = %s))"
        cur.execute(query, (container_uuid, function_uuid))

    if group is not None:
        app.logger.debug(f'Inserting group mapping: {group} : {function_uuid}')
        query = "INSERT into function_auth_groups (group_id, function_id) values (%s, %s)"
        cur.execute(query, (group, function_uuid))
    conn.commit()
    return function_uuid


def ingest_function(user_name, user_uuid, func_uuid, function_name, description, function_code, function_source, entry_point, container_uuid, group, public):
    """Ingest a function into Globus Search

    Restructures data for ingest purposes.

    Parameters
    ----------
    user_name : str
    user_uuid : str
    function_name : str
    description : str
    function_code : str
    function_source : str
    entry_point : str
    container_uuid : str
    group : str
    public : bool

    Returns
    -------
    None
    """
    data = {
        "function_name": function_name,
        "function_code": function_code,
        "function_source": function_source,
        "container_uuid": container_uuid,
        "entry_point": entry_point,
        "description": description,
        "public": public,
        "group": group
    }
    user_urn = f"urn:globus:auth:identity:{user_uuid}"
    models.search.func_ingest_or_update(func_uuid, data, author=user_name, author_urn=user_urn)


def ingest_endpoint(user_name, user_uuid, ep_uuid, data):
    owner_urn = f"urn:globus:auth:identity:{user_uuid}"
    models.search.endpoint_ingest_or_update(ep_uuid, data, owner=user_name, owner_urn=owner_urn)


def register_container(user_name, container_name, location, description, container_type):
    """Register the container in the database. Put an entry into containers and
    container_images

    Parameters
    ----------
    user_name : str
        The primary identity of the user
    container_name : str
        A name for the container
    location : str
        The path to the container
    description : str
        A description of the function
    container_type : str
        The container type

    Returns
    -------
    str
        The uuid of the container
    """
    user_id = resolve_user(user_name)
    container_uuid = str(uuid.uuid4())
    try:
        conn, cur = get_db_connection()

        query = "INSERT INTO containers (author, name, container_uuid, description) values (%s, %s, %s, %s)"
        cur.execute(query, (user_id, container_name, container_uuid, description))

        query = "INSERT INTO container_images (container_id, type, location) values (" \
                "(SELECT id from containers where container_uuid = %s), %s, %s)"
        cur.execute(query, (container_uuid, container_type, location))
        conn.commit()
    except Exception as e:
        print(e)
        app.logger.error(e)
    return container_uuid


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
    user_id = resolve_user(user_name)

    try:
        conn, cur = get_db_connection()
        if endpoint_uuid:
            # Check it is a valid uuid
            uuid.UUID(endpoint_uuid)

            # Check if the endpoint id already exists
            query = "SELECT * from sites where endpoint_uuid = %s"
            cur.execute(query, (endpoint_uuid, ))
            rows = cur.fetchall()
            if len(rows) > 0:
                # If it does, make sure the user owns it
                if rows[0]['user_id'] == user_id:
                    result_eid = endpoint_uuid
                    query = "UPDATE sites set endpoint_name = %s where endpoint_uuid = %s and user_id = %s"
                    cur.execute(query, (endpoint_name, endpoint_uuid, user_id))
                    conn.commit()
                    return result_eid
                else:
                    app.logger.debug(f"Endpoint {endpoint_uuid} was previously registered "
                                     f"with user {rows[0]['user_id']} not {user_id}")
                    return None
        else:
            endpoint_uuid = str(uuid.uuid4())

        query = "INSERT INTO sites (user_id, name, description, status, endpoint_name, endpoint_uuid) " \
                "values (%s, %s, %s, %s, %s, %s)"
        cur.execute(query, (user_id, '', description, 'OFFLINE', endpoint_name, endpoint_uuid))
        conn.commit()

    except Exception as e:
        app.logger.error(e)
        raise e
    return endpoint_uuid


def resolve_user(user_name):
    """Get the user id given their primary globus identity.

    Parameters
    ----------
    user_name : str
        The user's primary identity

    Returns
    -------
    int
        The user's id in the database
    """
    try:
        conn, cur = get_db_connection()
        query = "select * from users where username = %s limit 1"
        cur.execute(query, (user_name,))
        row = cur.fetchone()
        if row and 'id' in row:
            return row['id']
        else:
            # It failed to find the user so create a new record
            return create_user(user_name)
    except Exception as e:
        app.logger.error(f"Failed to find user identity {user_name}. {e}")
        raise UserNotFound("User ID could not be resolved for user_name: {}".format(user_name))


def create_user(user_name):
    """Insert the user into the database and return the resulting id.

    Parameters
    ----------
    user_name : str
        The user's primary globus identity

    Returns
    -------
    int the user's id in the database
    """
    try:
        conn, cur = get_db_connection()
        query = "insert into users (username) values (%s) returning id"
        cur.execute(query, (user_name, ))
        conn.commit()
        row = cur.fetchone()
        return row['id']
    except Exception as e:
        app.logger.error(f"Failed to create user identity {user_name}. {e}")
        raise


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


def delete_endpoint(user_name, endpoint_uuid):
    """Delete a function

    Parameters
    ----------
    user_name : str
        The primary identity of the user
    endpoint_uuid : str
        The uuid of the endpoint

    Returns
    -------
    str
        The result as a status code integer
            "302" for success and redirect
            "403" for unauthorized
            "404" for a non-existent or previously-deleted endpoint
            "500" for try statement error
    """
    try:
        conn, cur = get_db_connection()
        cur.execute(
            "SELECT username, sites.deleted FROM sites, users WHERE endpoint_uuid = %s AND sites.user_id = users.id",
            (endpoint_uuid,))
        site = cur.fetchone()
        if site is not None:
            if not site['deleted']:
                if site['username'] == user_name:
                    cur.execute("UPDATE sites SET deleted = True WHERE endpoint_uuid = %s", (endpoint_uuid,))
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
