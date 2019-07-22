from funcx.executors import HighThroughputExecutor as HTEX
from parsl.providers import LocalProvider
from parsl.channels import LocalChannel
from parsl import set_stream_logger
import time


def double(x):
    return x*2

if __name__ == "__main__" :

    set_stream_logger()

    executor = HTEX(label='htex',
                    provider=LocalProvider(
                        channel=LocalChannel),
                    address='34.207.74.221')

    ports = executor.start()
    print("Connect on ports {}".format(ports))


    print("Submitting")
    fu = executor.submit(double, *[2])
    print("Submitted")
    time.sleep(600)
          
    
