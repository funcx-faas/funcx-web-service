from config import load_funcx_client, get_db_connection
from flask import request, current_app as app

from globus_nexus_client import NexusClient
from globus_sdk import AccessTokenAuthorizer, GlobusAPIError

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
            client = load_funcx_client()
            auth_detail = client.oauth2_token_introspect(token)
            app.logger.debug(auth_detail)
            user_name = auth_detail['username']
        except Exception as e:
            print(e)
            abort(400, "Failed to authenticate user.")
        return f(user_name, *args, **kwargs)
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
    client = load_funcx_client()
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


def authorize_endpoint(user_name, endpoint_uuid, token):
    """Determine whether or not the user is allowed to access this endpoint.
    This is done in two steps: first, check if the user owns the endpoint. If not,
    check if there are any groups associated with the endpoint and determine if the user
    is a member of any of them.

    Parameters
    ----------
    user_name : str
        The primary identity of the user
    endpoint_uuid : str
        The uuid of the function
    token : str
        The auth token

    Returns
    -------
    bool
        Whether or not the user is allowed access to the endpoint
    """

    authorized = False
    try:
        conn, cur = get_db_connection()

        # Check if the user owns the endpoint
        query = "select * from sites, users where endpoint_uuid = %s and sites.user_id = users.id " \
                "and users.username = %s"
        cur.execute(query, (endpoint_uuid, user_name))
        if cur.fetchone() is not None:
            authorized = True
        else:
            # Check if there are any groups associated with this endpoint
            query = "select * from auth_groups where endpoint_id = %s"
            cur.execute(query, (endpoint_uuid,))
            rows = cur.fetchall()
            endpoint_groups = []
            for row in rows:
                endpoint_groups.append(row['group_id'])
            if len(endpoint_groups) > 0:
                authorized = check_group_membership(token, endpoint_groups)

    except Exception as e:
        print(e)
        app.logger.error(e)
    return authorized


def get_user(headers):
    """Get the user details from the database.

    Parameters
    ----------
    headers : dict
        The request headers

    Returns
    -------
    str
        The uuid of the user
    str
        The name of the user
    str
        The shortname of the user
    """

    globus_name = user_name
    short_name = None
    user_id = None

    app.logger.debug('Authorizing user: {}'.format(user_name))
    if not user_name:
        return None, None, None

    # Now check if it is in the database.
    try:
        conn, cur = get_db_connection()
        cur.execute("SELECT * from users where username = %s", (user_name,))
        rows = cur.fetchall()
        if len(rows) > 0:
            for r in rows:
                short_name = r['namespace']
                user_id = r['id']
        else:
            short_name = "{name}_{org}".format(name=user_name.split("@")[0], org=user_name.split("@")[1].split(".")[0])
            cmd = "INSERT into users (username, globus_identity, namespace) values (%s, %s, %s) RETURNING id"
            cur.execute(cmd, (user_name, globus_name, short_name))
            conn.commit()
            user_id = cur.fetchone()[0]
    except Exception as e:
        print(e)
        app.logger.error(e)
    return user_id, user_name, short_name

