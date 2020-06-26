import requests
import time
from funcx.sdk.client import FuncXClient
from funcx.serialize import FuncXSerializer


def get_result(task_id):
    """Get the result of the function.
    """
    fxc = FuncXClient(funcx_service_address='https://dev.funcx.org/api/v1')
    res = fxc.get_result(task_id)
    print(res)
    return res

def get_deser_result(task_id):
    """Get the result of the function.
    """
    fxc = FuncXClient(funcx_service_address='https://dev.funcx.org/api/v1')
    res = fxc.get(f"/tasks/{task_id}?deserialize=True")
    print(res)
    return res


def get_ser_result(task_id):
    """Get the result of the function.
    """
    fxc = FuncXClient(funcx_service_address='https://dev.funcx.org/api/v1')
    res = fxc.get(f"/tasks/{task_id}")
    print(res)
    return res


def test_func(blob):
#    return 'done'
    return blob['name']


def run_real(payload):
    """Run a function with some raw json input.
    """
    fxc = FuncXClient(funcx_service_address='https://dev.funcx.org/api/v1')

    # register a function
    func_id = fxc.register_function(test_func)
    ep_id = '60ad46e1-c912-468b-8674-4d582e9dc9ee'

    res = fxc.run({'name':'real'}, function_id = func_id, endpoint_id=ep_id)

    print(res)
    
    return res


def run_ser(payload):
    """Run a function with some raw json input.
    """
    fxc = FuncXClient(funcx_service_address='https://dev.funcx.org/api/v1')

    # register a function
    func_id = fxc.register_function(test_func)
    ep_id = '60ad46e1-c912-468b-8674-4d582e9dc9ee'
    payload = {'serialize': True,
               'payload': payload,
               'endpoint': ep_id,
               'func': func_id}

    res = fxc.post('submit', json_body=payload)
    res = res['task_uuid']
    print(res)

    return res

if __name__ == "__main__" : 
    payload = {'name': 'bob'}
#    task_id = '3a126e05-f551-4a0c-842b-a9d7308c53a7'

    # check things work normally
    print('try normally')
    task_id = run_real(payload)
    print(task_id)
    time.sleep(3)
    res = get_result(task_id)
    print(res)

    print('try raw json + serailizer')
    task_id = run_ser(payload)
    print(task_id)
    time.sleep(3)
    res = get_result(task_id)
    print(res)


    print('try raw json + serailized result')
    task_id = run_ser(payload)
    print(task_id)
    time.sleep(3)
    res = get_ser_result(task_id)
    print(res)


    print('try raw json + deserailizer')
    task_id = run_ser(payload)
    print(task_id)
    time.sleep(3)
    res = get_deser_result(task_id)
    print(res)

