from flask import jsonify
from funcx_common.response_errors import FuncxResponseError


def create_error_response(exception, jsonify_response=False):
    """Creates JSON object responses for errors that occur in the service.
    These responses can be sent back to the funcx SDK client to be decoded.
    They also have a "reason" property so that they are human-readable.
    Note that the returned JSON object will be a dict unless jsonify_response
    is enabled, in which case it will return JSON that Flask can respond with.
    This helper will not raise the exception passed in, it will only turn
    it into a JSON object.

    Parameters
    ==========

    exception : Exception
       Exception to convert to a JSON object
    jsonify_response : bool
       Whether or not to call 'jsonify' on the resulting dict

    Returns:
       JSON object, HTTP status code
    """
    if isinstance(exception, FuncxResponseError):
        # the pack method turns a FuncxResponseError into a record
        # which will become json
        response = exception.pack()
        status_code = int(exception.http_status_code)
    else:
        # if the error is not recognized as a FuncxResponseError, a generic
        # response of the same format will be sent back, indicating an
        # internal server error
        response = {
            "status": "Failed",
            "code": 0,
            "error_args": [],
            "reason": f"An unknown error occurred: {exception}",
            "http_status_code": 500,
        }
        status_code = 500

    if jsonify_response:
        response = jsonify(response)

    return response, status_code
