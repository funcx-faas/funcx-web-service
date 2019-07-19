import argparse

from funcx.queues import RedisQueue


def test(endpoint_id=None, hostname=None, port=None):
    print("-"*50)
    print("Endpoint_id: ", endpoint_id)
    print("hostname: ", hostname)
    print("-"*50)
    tasks_rq = RedisQueue(f'task_{endpoint_id}', hostname)
    results_rq = RedisQueue(f'result_{endpoint_id}', hostname)
    tasks_rq.connect()
    results_rq.connect()
    for i in range(10):
        tasks_rq.put("01", {'a': 1, 'b': 2})

    for i in range(10):
        print("Got task back: ", tasks_rq.get())
    res = results_rq.get(timeout=1)
    print("Result : ", res)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-a", "--address", required=True,
                        help="Hostname of the Redis server")
    parser.add_argument("-e", "--endpoint_id", required=True,
                        help="Endpoint_id")
    parser.add_argument("-p", "--port",
                        help="Port that the Redis server can be reached on")
    args = parser.parse_args()


    test(endpoint_id=args.endpoint_id,
         hostname=args.address,
         port=args.port)
