from funcx.utils.response_errors import FuncxResponseError
from flask import current_app as jsonify

def create_error_response(exception, as_json=False):

    if isinstance(exception, FuncxResponseError):
        response = {'status': 'Failed',
                    'code': exception.code,
                    'error_args': exception.error_args,
                    'reason': exception.reason}
    else:
        response = {'status': 'Failed',
                    'code': 0,
                    'error_args': [],
                    'reason': f'An unknown error occurred: {exception}'}

    if as_json:
        return jsonify(response)
    
    return response
