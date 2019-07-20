import json
import uuid
import datetime

from config import get_db_connection
from flask import request, current_app as app


def create_task(task):
    """Insert a task into the database.

    Parameters
    ----------
    task : dict
        The dictionary of the task
    """
    try:
        user_id = task['user_id']
        task_id = task['task_id']
        function_id = task['function_id']
        endpoint_id = task['endpoint_id']
        created_at = datetime.datetime.fromtimestamp(task['created_at'])
        modified_at = datetime.datetime.fromtimestamp(task['modified_at'])
        status = task['status']
        result = None
        if 'result' in task:
            result = task['result']
        elif 'reason' in task:
            result = task['reason']

        conn, cur = get_db_connection()
        query = "INSERT INTO tasks (user_id, task_id, function_id, endpoint_id, " \
                "created_at, modified_at, status) values (%s, %s, %s, %s, %s, %s, %s);"
        cur.execute(query, (user_id, task_id, function_id, endpoint_id, created_at, modified_at, status))

        # Add in a result if it is set
        if result:
            query = "insert into results (task_id, result) values (%s, %s)"
            cur.execute(query, (task_id, str(result)))

        conn.commit()

    except Exception as e:
        print(e)
        app.logger.error(e)


def register_function(user_name, function_name, description, function_code, entry_point, container_uuid):
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

    Returns
    -------
    str
        The uuid of the function
    """
    user_id = resolve_user(user_name)
    try:
        conn, cur = get_db_connection()
        function_uuid = str(uuid.uuid4())
        query = "INSERT INTO functions (user_id, name, description, status, function_name, function_uuid, " \
                "function_code, entry_point) values (%s, %s, %s, %s, %s, %s, %s, %s)"
        cur.execute(query, (user_id, '', description, 'REGISTERED', function_name,
                            function_uuid, function_code, entry_point))

        if container_uuid is not None:
            print(f'Inserting container mapping: {container_uuid}')
            query = "INSERT INTO function_containers (container_id, function_id) values (" \
                    "(SELECT id from containers where container_uuid = %s), " \
                    "(SELECT id from functions where function_uuid = %s))"
            print(query)
            cur.execute(query, (container_uuid, function_uuid))
        conn.commit()
    except Exception as e:
        print(e)
        app.logger.error(e)
    return function_uuid


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

        query = "INSERT INTO containers (author, name, container_uuid, description) values (%s, %s, %s, %s) RETURNING id"
        cur.execute(query, (user_id, container_name, container_uuid, description))
        container_id = cur.fetchone()[0]

        query = "INSERT INTO container_images (container_id, type, location) values (%s, %s, %s)"
        cur.execute(query, (container_id, container_type, location))
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
            # Make sure it exists
            query = "SELECT * from sites where user_id = %s and endpoint_uuid = %s"
            cur.execute(query, (user_id, endpoint_uuid))
            rows = cur.fetchall()
            if len(rows) > 0:
                return endpoint_uuid
        endpoint_uuid = str(uuid.uuid4())
        query = "INSERT INTO sites (user_id, name, description, status, endpoint_name, endpoint_uuid) " \
                "values (%s, %s, %s, %s, %s, %s)"
        cur.execute(query, (user_id, '', description, 'OFFLINE', endpoint_name, endpoint_uuid))
        conn.commit()
    except Exception as e:
        print(e)
        app.logger.error(e)
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
        return row['id']
    except Exception as e:
        app.logger.error(f"Failed to find user identity {user_name}. {e}")


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

    function_code = None
    function_entry = None
    container_uuid = None
    try:
        conn, cur = get_db_connection()
        query = "select * from functions where function_uuid = %s and user_id = %s order by id DESC limit 1"
        cur.execute(query, (function_uuid, user_id))
        r = cur.fetchone()
        function_code = r['function_code']
        function_entry = r['entry_point']
        function_id = r['id']
        query = "select * from function_containers, containers, container_images where " \
                "function_containers.function_id = %s and containers.id = function_containers.container_id " \
                "and function_containers.container_id = container_images.container_id " \
                "order by function_containers.id desc limit 1"
        cur.execute(query, (function_id,))
        r = cur.fetchone()
        try:
            container_uuid = r['container_uuid']
        except:
            pass
    except Exception as e:
        print(e)
        app.logger.error(e)
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
