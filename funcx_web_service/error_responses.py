from funcx.utils.response_errors import FuncxResponseError

def create_error_response(exception):

    if isinstance(exception, FuncxResponseError):
        response = exception.pack()
    else:
        response = {'status': 'Failed',
                    'code': 0,
                    'error_args': [],
                    'reason': f'An unknown error occurred: {exception}'}
    
    return response
