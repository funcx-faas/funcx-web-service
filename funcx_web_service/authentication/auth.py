from funcx_web_service.models.auth_groups import AuthGroup
from funcx_web_service.models.endpoint import Endpoint
from funcx_web_service.models.user import User
from funcx_web_service.models.function import Function, FunctionAuthGroup
from funcx.utils.response_errors import FunctionNotFound, EndpointNotFound, FunctionNotPermitted
from flask import request, current_app as app
import functools

from globus_nexus_client import NexusClient
from globus_sdk import AccessTokenAuthorizer, ConfidentialAppAuthClient

from functools import wraps
from flask import abort


def authenticated(f):
    """Decorator for globus auth."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'Authorization' not in request.headers:
            abort(401, 'You must be logged in to perform this function.')

        token = request.headers.get('Authorization')
        token = str.replace(str(token), 'Bearer ', '')
        user_name = None
        try:
            client = get_auth_client()
            auth_detail = client.oauth2_token_introspect(token)
            app.logger.debug(auth_detail)
            user_name = auth_detail['username']
            user_rec = User.resolve_user(user_name)

            if not user_rec:
                abort(400, description=f"User {user_name} not found in database.")

        except Exception as e:
            print(e)
            abort(400, "Failed to authenticate user.")
        return f(user_rec, *args, **kwargs)
    return decorated_function


def authenticated_w_uuid(f):
    """Decorator for globus auth."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'Authorization' not in request.headers:
            abort(401, 'You must be logged in to perform this function.')

        token = request.headers.get('Authorization')
        token = str.replace(str(token), 'Bearer ', '')
        user_name = None
        user_uuid = None
        try:
            client = get_auth_client()
            auth_detail = client.oauth2_token_introspect(token)
            app.logger.debug(auth_detail)
            user_name = auth_detail['username']
            user_uuid = auth_detail['sub']
            user_rec = User.resolve_user(user_name)

            if not user_rec:
                abort(400, description=f"User {user_name} not found in database.")

        except Exception as e:
            print(e)
            abort(400, "Failed to authenticate user.")
        return f(user_rec, user_uuid, *args, **kwargs)
    return decorated_function


def check_group_membership(token, endpoint_groups):
    """Determine whether or not the user is a member
    of any of the groups

    Parameters
    ----------
    token : str
        The user's nexus token
    endpoint_groups : list
        A list of the group ids associated with the endpoint

    Returns
    -------
    bool
        Whether or not the user is a member of any of the groups
    """
    client = get_auth_client()
    dep_tokens = client.oauth2_get_dependent_tokens(token)

    nexus_token = dep_tokens.by_resource_server['nexus.api.globus.org']["access_token"]

    # Create a nexus client to retrieve the user's groups
    nexus_client = NexusClient()
    nexus_client.authorizer = AccessTokenAuthorizer(nexus_token)
    user_groups = nexus_client.list_groups(my_statuses="active", fields="id", for_all_identities=True)

    # Check if any of the user's groups match
    for user_group in user_groups:
        for endpoint_group in endpoint_groups:
            if user_group['id'] == endpoint_group:
                return True
    return False


@functools.lru_cache()
def authorize_endpoint(user_id, endpoint_uuid, function_uuid, token):
    """Determine whether or not the user is allowed to access this endpoint.
    This is done in two steps: first, check if the user owns the endpoint. If not,
    check if there are any groups associated with the endpoint and determine if the user
    is a member of any of them.

    Raises an Exception if the endpoint does not exist, or if the endpoint is
    restricted and the provided function is not whitelisted.

    Parameters
    ----------
    user_id : str
        The primary identity of the user
    endpoint_uuid : str
        The uuid of the endpoint
    function_uuid : str
        The uuid of the function
    token : str
        The auth token

    Returns
    -------
    bool
        Whether or not the user is allowed access to the endpoint
    """

    authorized = False
    endpoint = Endpoint.find_by_uuid(endpoint_uuid)
    authorized = False

    if not endpoint:
        raise EndpointNotFound(endpoint_uuid)

    if endpoint.restricted:
        app.logger.debug("Restricted endpoint, checking function is allowed.")
        whitelisted_functions = [f.function_uuid for f in endpoint.restricted_functions]

        if function_uuid not in whitelisted_functions:
            raise FunctionNotPermitted(function_uuid, endpoint_uuid)

    if endpoint.public:
        authorized = True
    elif endpoint.user_id == user_id:
        authorized = True

    if not authorized:
        # Check if there are any groups associated with this endpoint
        groups = AuthGroup.find_by_endpoint_uuid(endpoint_uuid)
        endpoint_groups = [g.group_id for g in groups]
        if len(endpoint_groups) > 0:
            authorized = check_group_membership(token, endpoint_groups)

    return authorized


@functools.lru_cache()
def authorize_function(user_id, function_uuid, token):
    """Determine whether or not the user is allowed to access this function.
    This is done in two steps: first, check if the user owns the function. If not,
    check if there are any groups associated with the function and determine if the user
    is a member of any of them.

    Raises an Exception if the function does not exist.

    Parameters
    ----------
    user_id : str
        The primary identity of the user
    function_uuid : str
        The uuid of the function
    token : str
        The auth token

    Returns
    -------
    bool
        Whether or not the user is allowed access to the function
    """

    authorized = False
    function = Function.find_by_uuid(function_uuid)

    if not function:
        raise FunctionNotFound(function_uuid)

    if function.user_id == user_id:
        authorized = True
    elif function.public:
        authorized = True

    if not authorized:
        # Check if there are any groups associated with this function
        groups = FunctionAuthGroup.find_by_function_uuid(function_uuid)
        function_groups = [g.group_id for g in groups]

        if len(function_groups) > 0:
            authorized = check_group_membership(token, function_groups)

    return authorized


def get_auth_client():
    """
    Create an AuthClient for the portal
    """
    return ConfidentialAppAuthClient(app.config['GLOBUS_CLIENT'], app.config['GLOBUS_KEY'])
