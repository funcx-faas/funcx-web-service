First build the funcX web base image:
```bash
cd dockers/base
docker build -t funcx-web-base .
```
You'll need two secrets for the app to work properly, the funcX Globus Confidential Client ID and Key.
Place them in `dockers/secrets/globus_client.txt` and `dockers/secrets/globus_key.txt`.  **WARNING**: 
make sure to have the `dockers/secrets` directory in your `.gitignore` if it is not already.   

Then, from the main `funcx-web-service` directory, you can run:
```
docker-compose up
```
If any requirements in the API, Forwarder, or Serializer change, make sure to run: 
```bash
pip freeze > dockers/base/all-requirements.txt
docker-compose build
```