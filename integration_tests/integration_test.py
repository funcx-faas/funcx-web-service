from funcx.sdk.client import FuncXClient
endpoint = "4a55d09b-a4c3-4f02-8e9e-4e5371d73b54"

fxc = FuncXClient(funcx_service_address="http://localhost:5000/v1")
container = fxc.register_container("NCSA", "Docker", "test-image", "This is just a test")
print("Registered container ", container)

saved_container = fxc.get_container(container, "Docker")
print("Saved container ", saved_container)


def hello_world():
    return "Hello World!"


def hello_world2():
    return "so it goes"


func_uuid = fxc.register_function(hello_world)
task_id = fxc.run(endpoint_id=endpoint, function_id=func_uuid)
print(task_id)

func_container_uuid = fxc.register_function(hello_world, container_uuid=container)
print(func_uuid)


print(fxc.add_to_whitelist(endpoint, [func_uuid, func_container_uuid]))
print("White list", fxc.get_whitelist(endpoint))

print("Deleteing ", func_uuid, " from endpoint ", endpoint)
fxc.delete_from_whitelist(endpoint, [func_uuid])
# This doesn't actually do anything! Empty implementation in SDK
print("update function", fxc.update_function(func_uuid, hello_world2))
