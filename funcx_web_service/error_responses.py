from flask import jsonify

from funcx.utils.response_errors import FuncxResponseError

def create_error_response(exception, jsonify_response=False):

    if isinstance(exception, FuncxResponseError):
        response = exception.pack()
        status_code = int(exception.http_status_code)
    else:
        response = {'status': 'Failed',
                    'code': 0,
                    'error_args': [],
                    'reason': f'An unknown error occurred: {exception}'}
        status_code = 500
    
    if jsonify_response:
        response = jsonify(response)

    return response, status_code
