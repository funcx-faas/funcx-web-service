""" The broker service

This REST service fields incoming registration requests from endpoints,
creates an appropriate forwarderservice to which the endpoint can connect up.
"""


import bottle
from bottle import post, run, request, app, route, get
import argparse
import json
import uuid
import sys
import logging
import redis
import threading
from forwarderservice.forwarder import Forwarder, spawn_forwarder


@route('/ping')
def ping():
    """ Minimal liveness response
    """
    return "pong"


@get('/map.json')
def get_map_json():
    """ Paint a map of utilization
    """
    results = []
    redis_client = request.app.redis_client
    csv_string = "org,core_hrs,lat,long\n</br>"
    for key in redis_client.keys('ep_status_*'):
        try:
            print("Getting key {}".format(key))
            items = redis_client.lrange(key, 0, 0)
            if items:
                last = json.loads(items[0])
            else:
                continue
            ep_id = key.split('_')[2]
            ep_meta = redis_client.hgetall('endpoint:{}'.format(ep_id))
            print(ep_meta, last)
            lat, lon = ep_meta['loc'].split(',')
            current = {'org': ep_meta['org'].replace(',', '. '),
                       'core_hrs': last['total_core_hrs'],
                       'lat': lat,
                       'long': lon}
            results.append(current)

        except Exception as e:
            print(f"Failed to parse for key {key}")
            print(f"Error : {e}")

    print("To return : ", results)
    return dict(data=results)


@get('/map.csv')
def get_map():
    """ Paint a map of utilization
    """
    results = {"data": []}
    redis_client = request.app.redis_client
    csv_string = "org,core_hrs,lat,long\n</br>"
    for key in redis_client.keys('ep_status_*'):
        try:
            print("Getting key {}".format(key))
            items = redis_client.lrange(key, 0, 0)
            if items:
                last = json.loads(items[0])
            else:
                continue
            ep_id = key.split('_')[2]
            ep_meta = redis_client.hgetall('endpoint:{}'.format(ep_id))
            print(ep_meta, last)
            current = "{},{},{}\n</br>".format(ep_meta['org'].replace(',', '.'), last['total_core_hrs'], ep_meta['loc'])
            csv_string += current

        except Exception as e:
            print(f"Failed to parse for key {key}")
            print(f"Error : {e}")

    return csv_string


def wait_for_forwarder(fw):
    fw.join()

@post('/register')
def register():
    """ Register an endpoint request

    1. Start an executor client object corresponding to the endpoint
    2. Pass connection info back as a json response.
    """

    print("Request: ", request)
    print("foo: ", request.app.ep_mapping)
    print(json.load(request.body))
    endpoint_details = json.load(request.body)
    print(endpoint_details)

    # Here we want to start an executor client.
    # Make sure to not put anything into the client, until after an interchange has
    # connected to avoid clogging up the pipe. Submits will block if the client has
    # no endpoint connected.
    endpoint_id = endpoint_details['endpoint_id']
    fw = spawn_forwarder(request.app.address,
                         endpoint_details['redis_address'],
                         endpoint_id,
                         endpoint_addr=endpoint_details['endpoint_addr'],
                         logging_level=logging.DEBUG if request.app.debug else logging.INFO)

    connection_info = fw.connection_info

    fw_mon = threading.Thread(target=wait_for_forwarder, daemon=True, args=(fw,))
    fw_mon.start()

    ret_package = {'endpoint_id': endpoint_id}
    ret_package.update(connection_info)
    print("Ret_package : ", ret_package)

    print("Ep_id: ", endpoint_id)
    request.app.ep_mapping[endpoint_id] = ret_package
    return ret_package


@route('/list_mappings')
def list_mappings():
    return request.app.ep_mapping


def cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", default=8080,
                        help="Port at which the service will listen on")
    parser.add_argument("-a", "--address", required=True,
                        help="Address at which the service is running. This is the address passed to the endpoints")
    parser.add_argument("-c", "--config", default=None,
                        help="Config file")
    parser.add_argument("-r", "--redishost", required=True,
                        help="Redis host address")
    parser.add_argument("--redisport", default=6379,
                        help="Redis port")
    parser.add_argument("-d", "--debug", action='store_true',
                        help="Enables debug logging")

    args = parser.parse_args()

    app = bottle.default_app()
    app.address = args.address
    app.debug = args.debug
    app.ep_mapping = {}

    app.redis_client = redis.StrictRedis(host=args.redishost,
                                         port=int(args.redisport),
                                         decode_responses=True)

    try:
        run(host='0.0.0.0', app=app, port=int(args.port), debug=True)

    except Exception as e:
        # This doesn't do anything
        print("Caught exception : {}".format(e))
        exit(-1)


if __name__ == '__main__':
    cli()
