
from flask import Blueprint, request, g, abort, url_for, Response, jsonify
import json
import requests

automate_api = Blueprint("automate_api", __name__)


@automate_api.route("/<action_id>/release", methods=['GET'])
def execute_task_release(action_id):
   try:
       del (parsl_apps[action_id])
   except Exception as e:
       print(e)
       return json.dumps({"status": "Error"})
   return json.dumps({"status": "Released"})


@automate_api.route("/<action_id>/cancel", methods=['GET'])
def execute_task_cancel(action_id):
   try:
       pass
   except Exception as e:
       print(e)
       return {"status": "Error"}

   return json.dumps({"status": "TODO"})


@automate_api.route("/<action_id>/status", methods=['GET'])
def execute_task_status(action_id):
   print('In status check')

   status_req = requests.get('https://funcx.org/api/v1/{}/status'.format(action_id))
   print("Status response: {}".format(status_req.json))
   return json.dumps(status_req.json())

   status = "UNKNOWN"
   output = None
   try:
       tmp_app = parsl_apps[action_id]
       if tmp_app.done() == True:
           status = "SUCCEEDED"
           output = tmp_app.result()
   except Exception as e:
       print(e)
       pass
   if output:
       try:
           output = json.dumps(output)
           return json.dumps({"status": status, 'output': output})
       except:
           return json.dumps({"status": status})
   else:
       return json.dumps({"status": status})


@automate_api.route("/list", methods=['GET'])
def execute_list():
   actions = ["funcx"]
   return json.dumps(actions)


@automate_api.route("/funcx/introspect", methods=['GET'])
def execute_introspect():
   inputs = {"config_id": {"type": "string", "required": True},
             "command": {"type": "string", "required": True},
             "action_id": {"type": "string", "required": True}}
   return json.dumps(inputs)


@automate_api.route("/funcx/run", methods=['POST'])
def execute_run():

    print("RUNNING AUTOMATE API")

    if not request.json:
        abort(400)

    body = request.json

    command = body["command"]
    if 'async' not in body:
        body['async'] = True
    print("CMD: {}".format(command))

    template = None
    if 'template' in body:
        template = body["template"]
    #task_uuid = uuid.uuid4()
    cmd = command
    print('new cmd: ', cmd)
    is_async = False
    try:
        if template:
            cmd = cmd.format(**template)
    except:
        print('failed to template')

    # Minor TODO: Add errors around formatting of command.
    # TODO: Send task to queue (parsl).
    try:
        print("Executing Command: " + str(cmd))

        # Uncomment this for local
        # execute_task(str(cmd))
        parsl_req = requests.post('https://funcx.org/api/v1/execute', json = json.dumps(body))
        # parsl_req = requests.post("http://127.0.0.1:5001/run_parsl_task", data = {'cmd':cmd, 'is_async': is_async})
        print("PARSL response: {}".format(parsl_req.json))

    except Exception as e:
        print("AUTOMATE EXECUTE ERROR: " + str(e))

    print("Returning data to automate:")
    task_id = parsl_req.json()['task_id']
    print(task_id)
    return task_id
