from flask import Response


class FuncxResponseLogData:
    def __init__(self):
        self.data = {}

    def set_user(self, user):
        self.data["user_id"] = user.id


class FuncxResponse(Response):
    def __init__(self, *args, **kwargs):
        self._log_data = FuncxResponseLogData()
        super().__init__(*args, **kwargs)
