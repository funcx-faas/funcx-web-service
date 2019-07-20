from config import load_funcx_client, get_db_connection
from flask import request, current_app as app

from globus_nexus_client import NexusClient
from globus_sdk import AccessTokenAuthorizer, GlobusAPIError


def authorize_endpoint(user_id, endpoint_uuid, token):
    """Get the endpoint uuid from database

    Parameters
    ----------
    user_id : int
        The database id of the user
    endpoint_uuid : str
        The uuid of the function
    token : str
        The auth token

    Returns
    -------
    boolean
        Whether or not the user is allowed access to the endpoint
    """

    try:
        conn, cur = get_db_connection()

        # Check if there are any groups associated with this endpoint
        query = "select * from auth_groups where endpoint_id = %s"
        cur.execute(query, (endpoint_uuid,))
        rows = cur.fetchall()
        endpoint_groups = []
        for row in rows:
            endpoint_groups.append(row['group_id'])

        if len(endpoint_groups) > 0:
            # Check if the user is in one of these groups
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
        else:
            # Check if the user owns this endpoint
            query = "select * from sites where endpoint_uuid = %s and user_id = %s order by id DESC limit 1"
            cur.execute(query, (endpoint_uuid, user_id))
            row = cur.fetchone()
            endpoint_uuid = row['endpoint_uuid']
            if not endpoint_uuid:
                return False

    except Exception as e:
        print(e)
        app.logger.error(e)
        return False
    return True


def introspect_token(headers):
    """
    Decode the token and retrieve the user's details

    Parameters
    ----------
    headers : dict
        The request headers

    Returns
    -------
    str
        The name of the user
    """
    user_name = None
    if 'Authorization' in headers:
        token = request.headers.get('Authorization')
        app.logger.debug(token)
        token = token.split(" ")[1]
        try:
            client = load_funcx_client()
            auth_detail = client.oauth2_token_introspect(token)
            app.logger.debug(auth_detail)
            user_name = auth_detail['username']
        except Exception as e:
            print(e)
            app.logger.error('Auth error:', e)
    return user_name


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

    user_name = introspect_token(headers)
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

