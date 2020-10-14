from funcx.sdk.client import FuncXClient
endpoint = "ff465080-956f-46cb-9bed-866a45b07c14"

fxc = FuncXClient(funcx_service_address="http://localhost:5000/v1")
container = fxc.register_container("NCSA", "Docker", "test-image", "This is just a test")
print("Registered container ", container)

saved_container = fxc.get_container(container, "Docker")
print("Saved container ", saved_container)


def hello_world():
    return "Hello World!"


func_uuid = fxc.register_function(hello_world)

func_container_uuid = fxc.register_function(hello_world, container_uuid=container)
print(func_uuid)


print(fxc.add_to_whitelist(endpoint, [func_uuid, func_container_uuid]))
print("White list", fxc.get_whitelist(endpoint))
