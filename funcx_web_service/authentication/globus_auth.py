import globus_sdk
from flask import abort, current_app


def introspect_token(
    token: str, *, verify: bool = True
) -> globus_sdk.GlobusHTTPResponse:
    client = get_auth_client()
    data = client.oauth2_token_introspect(token)
    if verify:
        if not data.get("active", False):
            abort(401, "Credentials are inactive.")
    return data


# FIXME:
# this should be only creating a single client per web worker, not a new one per call
def get_auth_client():
    """Create an AuthClient for the service."""
    return globus_sdk.ConfidentialAppAuthClient(
        current_app.config["GLOBUS_CLIENT"], current_app.config["GLOBUS_KEY"]
    )
