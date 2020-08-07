import argparse
import uuid
from forwarderservice.forwarder import Forwarder, spawn_forwarder
import time


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", default=8080,
                        help="Port at which the service will listen on")
    parser.add_argument("-a", "--address", default='34.207.74.221',
                        help="Address at which the service is running")
    parser.add_argument("-e", "--endpoint_id", default=None,
                        help="Endpoint id")
    parser.add_argument("-d", "--debug", action='store_true',
                        help="Enables debug logging")

    args = parser.parse_args()

    redis_address = "funcx-redis.wtgh6h.0001.use1.cache.amazonaws.com"

    fw = spawn_forwarder(args.address,
                         redis_address,
                         args.endpoint_id)
    print(fw.connection_info)
    time.sleep(10)
    print(fw)

    
