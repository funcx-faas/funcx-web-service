import argparse
import time

import funcx
from funcx import FuncXClient


def container_sum(event):
    return sum(event)


def test(fxc, ep_id):
    container_uuid = fxc.register_container(
        "docker.io/swansonkirk80/nonconformity:latest", container_type="docker"
    )
    print("Container uuid :", container_uuid)
    fn_uuid = fxc.register_function(
        container_sum,
        container_uuid=container_uuid,
        description="New sum function defined without string spec",
    )
    print("FN_UUID : ", fn_uuid)
    task_id = fxc.run([1, 2, 3, 9001], endpoint_id=ep_id, function_id=fn_uuid)
    while True:
        try:
            x = fxc.get_result(task_id)
            print(x)
            break
        except Exception as e:
            print("Got exception: ", type(e), e)
            time.sleep(3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-e", "--endpoint", default="3219a68c-32e5-46b0-8d7a-d94c2578af0a"
    )
    args = parser.parse_args()
    print("FuncX version : ", funcx.__version__)
    fxc = FuncXClient(funcx_service_address="http://localhost:5000/v2")
    test(fxc, args.endpoint)
