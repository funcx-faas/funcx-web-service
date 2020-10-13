from funcx.sdk.client import FuncXClient

fxc = FuncXClient(funcx_service_address="http://localhost:5000/v1")


def hello_world():
    return "Hello World!"


func_uuid = fxc.register_function(hello_world)
print(func_uuid)


print(fxc.add_to_whitelist("ff465080-956f-46cb-9bed-866a45b07c14", [func_uuid]))
