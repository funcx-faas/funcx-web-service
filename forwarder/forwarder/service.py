""" The broker service

This REST service fields incoming registration requests from endpoints,
creates an appropriate forwarder to which the endpoint can connect up.
"""


import argparse
import json
import logging
import redis
import threading

from flask import Flask, jsonify
from flask import request

from forwarder.version import VERSION, MIN_EP_VERSION
from forwarder.forwarderobject import spawn_forwarder


app = Flask(__name__)


@app.route('/ping')
def ping():
    """ Minimal liveness response
    """
    return "pong"


@app.route('/version')
def version():
    return jsonify({
        "forwarder": VERSION,
        "min_ep_version": MIN_EP_VERSION
    })


@app.route('/map.json', methods=['GET'])
def get_map_json():
    """ Paint a map of utilization
    """
    results = []
    redis_client = app.config['redis_client']
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


@app.route('/map.csv', methods=['GET'])
def get_map():
    """ Paint a map of utilization
    """
    results = {"data": []}
    redis_client = app.config['redis_client']
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


@app.route('/register', methods=['POST'])
def register():
    """ Register an endpoint request

    1. Start an executor client object corresponding to the endpoint
    2. Pass connection info back as a json response.
    """

    print("Request: ", request)
    print("foo: ", app.config['ep_mapping'])
    print(request.get_json())
    endpoint_details = request.get_json()
    print(endpoint_details)

    # Here we want to start an executor client.
    # Make sure to not put anything into the client, until after an interchange has
    # connected to avoid clogging up the pipe. Submits will block if the client has
    # no endpoint connected.
    endpoint_id = endpoint_details['endpoint_id']
    fw = spawn_forwarder(app.config['address'],
                         endpoint_details['redis_address'],
                         endpoint_id,
                         endpoint_addr=endpoint_details['endpoint_addr'],
                         logging_level=logging.DEBUG if app.debug else logging.INFO)

    connection_info = fw.connection_info

    fw_mon = threading.Thread(target=wait_for_forwarder, daemon=True, args=(fw,))
    fw_mon.start()

    ret_package = {'endpoint_id': endpoint_id}
    ret_package.update(connection_info)
    print("Ret_package : ", ret_package)

    print("Ep_id: ", endpoint_id)
    app.config['ep_mapping'][endpoint_id] = ret_package
    return ret_package


@app.route('/list_mappings')
def list_mappings():
    return app.config['ep_mapping']


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

    app.config['address'] = args.address
    app.config['ep_mapping'] = {}

    app.config['redis_client'] = redis.StrictRedis(
        host=args.redishost,
        port=int(args.redisport),
        decode_responses=True
    )

    try:
        print("Starting forwarder service")
        app.run(host='0.0.0.0', port=int(args.port), debug=True)

    except Exception as e:
        # This doesn't do anything
        print("Caught exception : {}".format(e))
        exit(-1)


if __name__ == '__main__':
    print("entering forwarder service main.........")
    cli()
