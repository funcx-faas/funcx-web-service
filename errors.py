class FuncxError(Exception):
    """ Base class for all Forwarder exceptions
    """

    def __init__(self, reason):
        self.reason = reason

    def __str__(self):
        return self.__repr__()

class UserNotFound(FuncxError):
    """ Base class for all Forwarder exceptions
    """

    def __init__(self, reason):
        self.reason = reason

    def __str__(self):
        return self.__repr__()
