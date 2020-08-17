from funcx.sdk.client import FuncXClient
import os
import json

fxc = FuncXClient(funcx_service_address="http://localhost:5000/api/v1", force_login=False)
token_file = os.path.join(fxc.TOKEN_DIR, fxc.TOKEN_FILENAME)
with open(token_file) as f:
  data = json.load(f)
  print(data["funcx_service"]['access_token'])
