import zmq

class ZMQBroker():

    def start(self, ip_address="*", port=50000):
        """
        Start the broker
        :return:
        """
        print("Starting broker")
        # Prepare our context and sockets
        context = zmq.Context()
        frontend = context.socket(zmq.ROUTER)
        backend = context.socket(zmq.DEALER)
        frontend.bind("tcp://*:%s" % port)
        backend.bind("tcp://*:50001")

        # Initialize poll set
        poller = zmq.Poller()
        poller.register(frontend, zmq.POLLIN)
        poller.register(backend, zmq.POLLIN)

        # Switch messages between sockets
        while True:
            socks = dict(poller.poll())

            if socks.get(frontend) == zmq.POLLIN:
                message = frontend.recv_multipart()
                backend.send_multipart(message)

            if socks.get(backend) == zmq.POLLIN:
                message = backend.recv_multipart()
                print(message)
                frontend.send_multipart(message)

def start_broker():
    """
    Start the ZMQ broker. This allows multiple workers to submit requests.
    """
    try:
        broker = ZMQBroker()
        broker.start("*", 50000)
    except Exception as e:
        print("Broker failed. %s" % e)
        print("Continuing without a broker.")

if __name__ == "__main__":
    # Start the broker
    start_broker()
    print('done')
