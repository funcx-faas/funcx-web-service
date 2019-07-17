
class FuncxError(Exception):
    """ Base class for all Forwarder exceptions
    """

    def __str__(self):
        return self.__repr__()

