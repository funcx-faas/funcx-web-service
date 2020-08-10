import requests

from flask import request, current_app as app


def serialize_inputs(input_data):
    """Use the serialization service to encode input data.

    Parameters
    ----------
    input_data : str
        The input data to pass to ther serializer

    Returns
    -------
    str : The encoded data
    """
    ser_addr = app.config['SERIALIZATION_ADDR']
    ser_port = app.config['SERIALIZATION_PORT']

    res = requests.post(f'http://{ser_addr}:{ser_port}/serialize', json=input_data)
    if res.status_code == 200:
        return res.json()

    return None


def deserialize_result(result):
    """Use the serialization service to decode result.

    Parameters
    ----------
    result : str
        The data to pass to the deserializer

    Returns
    -------
    str : The decoded data
    """
    ser_addr = app.config['SERIALIZATION_ADDR']
    ser_port = app.config['SERIALIZATION_PORT']

    res = requests.post(f'http://{ser_addr}:{ser_port}/deserialize', json=result)
    if res.status_code == 200:
        return res.json()

    return None
