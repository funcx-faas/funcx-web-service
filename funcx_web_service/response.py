from flask import Response


class FuncxResponse(Response):
    def __init__(self, response, **kwargs):
        return super().__init__(response, **kwargs)
