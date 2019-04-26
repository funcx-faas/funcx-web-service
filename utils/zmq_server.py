import zmq


class ZMQServer(object):
    """
    Manage the ZMQ server to transmit requests.
    """

    def __init__(self, ip_address="localhost", port=50000):
        try:
            # Bind to the broker
            context = zmq.Context()
            self.server = context.socket(zmq.REQ)
            print("Starting server on {}:{}".format(ip_address, port))
            self.server.connect("tcp://{}:{}".format(ip_address, port))
        except Exception as e:
            print("Something went wrong binding REQ. %s" % e)

    def request(self, msg):
        """
        Transmit the request

        :param msg:
        :return:
        """
        print("Sent request.")
        self.server.send(msg)
        reply = self.server.recv()
        return reply
