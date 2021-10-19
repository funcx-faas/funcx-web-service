class FuncxError(Exception):
    """Base class for all web service exceptions not related to service responses
    (for web service response exceptions, see: funcx_common.response_errors)
    """

    def __init__(self, reason):
        self.reason = reason

    def __str__(self):
        return self.__repr__()
