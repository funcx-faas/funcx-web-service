class FuncxError(Exception):
    """ Base class for all web service exceptions
    """

    def __init__(self, reason):
        self.reason = reason

    def __str__(self):
        return self.__repr__()


class UserNotFound(FuncxError):
    """ User not found exception
    """

    def __init__(self, reason):
        self.reason = reason
    
    def __repr__(self):
        return self.reason


class FunctionNotFound(FuncxError):
    """ Function could not be resolved from the database
    """
    def __init__(self, uuid):
        self.reason = "Function {} could not be resolved".format(uuid)
        self.uuid = uuid
    
    def __repr__(self):
        return self.reason


class EndpointNotFound(FuncxError):
    """ Endpoint could not be resolved from the database
    """
    def __init__(self, uuid):
        self.reason = "Endpoint {} could not be resolved".format(uuid)
        self.uuid = uuid

    def __repr__(self):
        return self.reason


class FunctionNotPermitted(FuncxError):
    """ Function not permitted on endpoint
    """
    def __init__(self, function_uuid, endpoint_uuid):
        self.reason = "Function {} not permitted on endpoint {}".format(function_uuid, endpoint_uuid)
        self.function_uuid = function_uuid
        self.endpoint_uuid = endpoint_uuid

    def __repr__(self):
        return self.reason

class ForwarderRegistrationError(FuncxError):
    """ Registering the endpoint with the forwarder has failed
    """

    def __init__(self, reason):
        self.reason = reason

    def __repr__(self):
        return "Endpoint registration with forwarder failed due to {}".format(self.reason)
