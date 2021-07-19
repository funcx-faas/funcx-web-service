import time
import uuid

import redis
from flask import current_app as app

from funcx_web_service.models import search
from funcx.utils.response_errors import FunctionNotFound, EndpointAlreadyRegistered
from funcx_web_service.models.endpoint import Endpoint
from funcx_web_service.models.function import Function
from funcx_web_service.models.tasks import DBTask
from funcx_web_service.models.user import User


class db_invocation_logger(object):

    def log(self, user_id, task_id, function_id, endpoint_id, deferred=False):
        try:
            status = 'CREATED'
            task_record = DBTask(
                user_id=user_id,
                function_id=function_id,
                endpoint_id=endpoint_id,
                status=status
            )
            task_record.save_to_db()
        except Exception:
            app.logger.exception("Caught error while writing log update to db")

    def commit(self):
        pass


def add_ep_whitelist(user: User, endpoint_uuid, functions):
    """Add a list of function to the endpoint's whitelist.

    This function is only allowed by the owner of the endpoint.

    Parameters
    ----------
    user : User
        The user making the request
    endpoint_uuid : str
        The uuid of the endpoint to add the whitelist entries for
    functions : list
        A list of the function ids to add to the whitelist.

    Returns
    -------
    json
        The result of adding the functions to the whitelist
    """

    user_id = user.id

    endpoint = Endpoint.find_by_uuid(endpoint_uuid)

    if not endpoint:
        return {'status': 'Failed',
                'reason': f'Endpoint {endpoint_uuid} is not found in database'}

    if endpoint.user_id != user_id:
        return {'status': 'Failed',
                'reason': f'Endpoint does not belong to User {user.username}'}

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


def get_ep_whitelist(user: User, endpoint_id):
    """Get the list of functions in an endpoint's whitelist.

    This function is only allowed by the owner of the endpoint.

    Parameters
    ----------
    user : User
        The name of the user making the request
    endpoint_id : str
        The uuid of the endpoint to add the whitelist entries for

    Returns
    -------
    json
        The functions in the whitelist
    """

    endpoint = Endpoint.find_by_uuid(endpoint_id)
    if not endpoint:
        return {'status': 'Failed',
                'reason': f'Could not find endpoint  {endpoint_id}'}

    if endpoint.user != user:
        return {'status': 'Failed',
                'reason': f'User {user.username} is not authorized to perform this action on endpoint {endpoint_id}'}

    functions = [f.function_uuid for f in endpoint.restricted_functions]
    return {'status': 'Success', 'result': functions}


def delete_ep_whitelist(user: User, endpoint_id, function_id):
    """Delete the functions from an endpoint's whitelist.

    This function is only allowed by the owner of the endpoint.

    Parameters
    ----------
    user : User
        The the user making the request
    endpoint_id : str
        The uuid of the endpoint to add the whitelist entries for
    function_id : str
        The uuid of the function to remove from the whitelist

    Returns
    -------
    json
        A dict describing the success or failure of removing the function
    """

    saved_endpoint = Endpoint.find_by_uuid(endpoint_id)
    if not saved_endpoint:
        return {'status': 'Failed',
                'reason': f'Endpoint {endpoint_id} not found in database'}

    if saved_endpoint.user != user:
        return {'status': 'Failed',
                'reason': f'User {user.username} is not authorized to perform this action on endpoint {endpoint_id}'}

    saved_function = Function.find_by_uuid(function_id)

    if not saved_function:
        return {'status': 'Failed',
                'reason': f'Function {function_id} not found in database'}

    saved_endpoint.delete_whitelist_for_function(saved_function)
    return {'status': 'Success', 'result': function_id}


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
    selected_group = None if not function.auth_groups else function.auth_groups[0].group_id
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


def register_endpoint(user: User, endpoint_name, description, endpoint_uuid=None):
    """Register the endpoint in the database.

    Parameters
    ----------
    user : User
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
    user_id = user.id

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
                raise EndpointAlreadyRegistered(endpoint_uuid)
    else:
        endpoint_uuid = str(uuid.uuid4())
    try:
        new_endpoint = Endpoint(user=user,
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

    saved_function = Function.find_by_uuid(function_uuid)

    if not saved_function:
        raise FunctionNotFound(function_uuid)

    function_code = saved_function.function_source_code
    function_entry = saved_function.entry_point

    if saved_function.container:
        container_uuid = saved_function.container.container.container_uuid
    else:
        container_uuid = None

    delta = time.time() - start
    app.logger.info("Time to fetch function {0:.1f}ms".format(delta * 1000))
    return function_code, function_entry, container_uuid


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

    saved_function = Function.find_by_uuid(function_uuid)
    if not saved_function or saved_function.deleted:
        return 404

    saved_user = User.resolve_user(user_name)

    if not saved_user or saved_function.user != saved_user:
        return 403

    saved_function.function_name = function_name
    saved_function.function_desc = function_desc
    saved_function.function_entry_point = function_entry_point
    saved_function.function_source_code = function_code
    saved_function.save_to_db()
    return 302


def delete_function(user: User, function_uuid):
    """Delete a function

    Parameters
    ----------
    user : User
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
    saved_function = Function.find_by_uuid(function_uuid)
    if not saved_function or saved_function.deleted:
        return 404

    if saved_function.user != user:
        return 403

    saved_function.deleted = True
    saved_function.save_to_db()
    return 302
