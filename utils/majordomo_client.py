import logging

import zmq
import sys
from utils import MDP
#import MDP
#from zhelpers import dump
from utils.zhelpers import dump
import pickle

class ZMQClient(object):
    """Majordomo Protocol Client API, Python version.

      Implements the MDP/Worker spec at http:#rfc.zeromq.org/spec:7.
    """
    broker = None
    ctx = None
    client = None
    poller = None
    timeout = 2500
    timeout = 6000000
    retries = 1
    verbose = False

    def __init__(self, broker, verbose=False):
        self.broker = broker
        self.verbose = verbose
        self.ctx = zmq.Context()
        self.poller = zmq.Poller()
        logging.basicConfig(format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
                level=logging.INFO)
        self.reconnect_to_broker()

    def reconnect_to_broker(self):
        """Connect or reconnect to broker"""
        if self.client:
            self.poller.unregister(self.client)
            self.client.close()
        self.client = self.ctx.socket(zmq.REQ)
        self.client.linger = 0
        self.client.connect(self.broker)
        self.poller.register(self.client, zmq.POLLIN)
        if self.verbose:
            logging.info("I: connecting to broker at %s…", self.broker)

    def send(self, service, request):
        """Send request to broker and get reply by hook or crook.

        Takes ownership of request message and destroys it when sent.
        Returns the reply message or None if there was no reply.
        """
        request = [pickle.dumps(request)]    
        request = [MDP.C_CLIENT, pickle.dumps(service)] + request
        #if self.verbose:
        logging.warn("I: send request to '%s' service: ", service)
#        dump(request)
        reply = None

        retries = self.retries
        while retries > 0:
            self.client.send_multipart(request)
            try:
                items = self.poller.poll(self.timeout)
            except KeyboardInterrupt:
                break # interrupted

            if items:
                msg = self.client.recv_multipart()
                if self.verbose:
                    logging.info("I: received reply:")
                    dump(msg)

                # Don't try to handle errors, just assert noisily
                assert len(msg) >= 3

                header = msg.pop(0)
                assert MDP.C_CLIENT == header

                reply_service = msg.pop(0)
                assert service == pickle.loads(reply_service)

                reply = msg.pop(0)
                break
            else:
                if retries:
                    logging.warn("W: no reply, reconnecting…")
                    self.reconnect_to_broker()
                else:
                    logging.warn("W: permanent error, abandoning")
                    break
                retries -= 1

        return reply

    def destroy(self):
        self.context.destroy()

def main():
    verbose = '-v' in sys.argv
    client = ZMQClient("tcp://localhost:50001", verbose)
    count = 0
    import time
    import random
    start = time.time()
    while count < 100:
        service = "echo{}".format(random.randint(0, 0))
        request = "Hello world to service {}".format(service)
        request *= 100
        try:
            reply = client.send(service, request)
            # print(pickle.loads(reply))
        except KeyboardInterrupt:
            break
        else:
            # also break on failure to reply:
            if reply is None:
                break
        count += 1
    end = time.time()
    print("{} requests/replies processed in {} seconds".format(count, end-start))

if __name__ == '__main__':
    main()
