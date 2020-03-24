import time
import requests

from funcx.serialize import FuncXSerializer

def deserialize(payload):
    """Try to deserialize some input and return the result.
    """
    res = requests.post('http://localhost:8000/deserialize', json=payload)
    print(res.status_code)
    return res.json()

def serialize(payload):
    """Try to serialize some input and return the result.
    """
    res = requests.post('http://localhost:8000/serialize', json=payload)
    print(res.status_code)
    return res.json()

if __name__ == "__main__" : 
    payload = {'name': 'bob'}
    print(f'Input: {payload}')
    x = serialize(payload)
    print(f'Serialized: {x}')

    # Trim off kwargs (part 2 of the buffer)

    fx_serializer = FuncXSerializer()
    res = fx_serializer.unpack_buffers(x)
    print(res)
    y = deserialize(res[0])
    print(f'Deserialized: {y}')
 
    print('now break things')
    z = deserialize(res)
    print(z)

