from flask import Response


class FuncxResponseLogData:
    def __init__(self):
        self.data = {}

    def set_user(self, user):
        self.data["user_id"] = user.id

    def set_data(self, user=None, task=None, endpoint_id=None):
        if user:
            self.set_user(user)

        if task:
            self.data["task_id"] = task.id

        if endpoint_id:
            self.data["endpoint_id"] = endpoint_id


class FuncxResponse(Response):
    def __init__(self, response, **kwargs):
        self._log_data = FuncxResponseLogData()
        super().__init__(response, **kwargs)
