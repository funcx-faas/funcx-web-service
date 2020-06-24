from flask import request
from globus_sdk import AccessTokenAuthorizer, SearchClient, SearchAPIError

from authentication.auth import get_auth_client

SEARCH_INDEX_NAME = 'funcx'
SEARCH_INDEX_ID = '673a4b58-3231-421d-9473-9df1b6fa3a9d'
SEARCH_SCOPE = 'urn:globus:auth:scope:search.api.globus.org:all'

# Search limit defined by the globus API
SEARCH_LIMIT = 10000

# By default we will return 10 functions at a time
DEFAULT_SEARCH_LIMIT = 10


def get_search_client():
    """Creates a Globus Search Client using FuncX's client token"""
    auth_client = get_auth_client()
    tokens = auth_client.oauth2_client_credentials_tokens(requested_scopes=[SEARCH_SCOPE])
    search_token = tokens.by_scopes[SEARCH_SCOPE]
    authorizer = AccessTokenAuthorizer(search_token)
    search_client = SearchClient(authorizer)
    return search_client


def _trim_func_data(func_data):
    """Remove unnecessary fields from FuncX function metadata for ingest

    Parameters
    ----------
    func_data : dict
        the data put into redis for a function

    Returns
    -------
    dict
        a dict with the fields we want in search, notably including an author field
    """
    return {
        'function_name': func_data['function_name'],
        'function_code': func_data['function_code'],
        'function_source': func_data['function_source'],
        'container_uuid': func_data.get('container_uuid', ''),
        'description': func_data['description'],
        'public': func_data['public'],
        'group': func_data['group'],
        'author': ''
    }


def _exists(client, func_uuid):
    """Checks if a func_uuid exists in the search index

    Mainly used to determine whether we need a create or an update call to the search API

    Parameters
    ----------
    func_uuid : str
        the uuid of the function

    Returns
    -------
    bool
        True if `func_uuid` is a subject in Globus Search index
    """
    try:
        res = client.get_entry(SEARCH_INDEX_ID, func_uuid)
        return len(res.data['entries']) > 0
    except SearchAPIError as err:
        if err.http_status == 404:
            return False
        raise err


def ingest_or_update(func_uuid, func_data, author="", author_urn=""):
    """Update or create a function in search index

    Parameters
    ----------
    func_uuid : str
    func_data : dict
    author : str
    author_urn : str
    """
    client = get_search_client()
    acl = []
    if func_data['public']:
        acl.append('public')
    elif func_data['group']:
        acl.append(func_data['group'])

    # Ensure that the author of the function and the funcx search admin group have access
    # TODO: do we want access to everything? Is this the default since we control the index?
    acl.append(author_urn)
    acl.append('urn:globus:groups:id:69e12e30-b499-11ea-91c1-0a0ee5aecb35')

    content = _trim_func_data(func_data)
    content['author'] = author
    content['version'] = '0'

    ingest_data = {
        'subject': func_uuid,
        'visible_to': acl,
        'content': content
    }

    # Since we associate only 1 entry with each subject (func_uuid), there is basically
    # no difference between creating and updating, other than the method...

    if not _exists(client, func_uuid):
        client.create_entry(SEARCH_INDEX_ID, ingest_data)
    else:
        client.update_entry(SEARCH_INDEX_ID, ingest_data)
