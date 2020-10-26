import sys
import time
from funcx.sdk.client import FuncXClient
endpoint = "4a55d09b-a4c3-4f02-8e9e-4e5371d73b54"

if len(sys.argv) > 0:
    endpoint = sys.argv[1]

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


# Check batch requests are working
def test_batch1(a, b, c=2, d=2):
    return a + b + c + d


def test_batch2(a, b, c=2, d=2):
    return a * b * c * d


def test_batch3(a, b, c=2, d=2):
    return a + 2 * b + 3 * c + 4 * d


funcs = [test_batch1, test_batch2, test_batch3]
func_ids = []
for func in funcs:
    func_ids.append(fxc.register_function(func, description='test'))

start = time.time()
task_count = 5
batch = fxc.create_batch()
for func_id in func_ids:
    for i in range(task_count):
        batch.add(i, i+1, c=i+2, d=i+3, endpoint_id=endpoint, function_id=func_id)

task_ids = fxc.batch_run(batch)

delta = time.time() - start
print("Time to launch {} tasks: {:8.3f} s".format(task_count * len(func_ids), delta))
print("Got {} tasks_ids ".format(len(task_ids)))

for i in range(10):
    x = fxc.get_batch_status(task_ids)
    complete_count = sum([ 1 for t in task_ids if t in x and not x[t].get('pending', True) ])
    print("Batch status : {}/{} complete".format(complete_count, len(task_ids)))
    if complete_count == len(task_ids):
        print(x)
        break
    time.sleep(5)


# Verify exception deserialization
def failing():
    raise Exception("deterministic failure")


failing_function = fxc.register_function(failing)

res = fxc.run(endpoint_id=endpoint, function_id=failing_function)

try:
    fxc.get_result(res)
except Exception as e:
    print(e)

# Check task status updates
def funcx_sleep(val):
    import time
    time.sleep(int(val))
    return 'done'


func_uuid = fxc.register_function(funcx_sleep, description="A sleep function")

# check for pending status
print('check pending')
payload = 2
res = fxc.run(payload, endpoint_id=endpoint, function_id=func_uuid)
print(res)
try:
    print(fxc.get_result(res))
except Exception as e:
    print(e)
    pass

# Check for done
print('check done')
time.sleep(3)
print(fxc.get_result(res))

# check for running
print('check running')
payload = 90
res = fxc.run(payload, endpoint_id=endpoint, function_id=func_uuid)
print(res)
time.sleep(60)
try:
    print(fxc.get_result(res))
except Exception as e:
    print(e)
print('check still running')
try:
    print(fxc.get_result(res))
except Exception as e:
    print(e)
    pass
    pass

print('check done')
time.sleep(32)
print(fxc.get_result(res))


