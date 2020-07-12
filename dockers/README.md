First build the funcX web base image:
```bash
cd dockers/base
docker build -t funcx-web-base .
```
You'll need a few secrets for the app to work properly.  First, let's do the Globus secrets: the funcX Globus Confidential Client ID and Key.
Place them in `dockers/secrets/globus_client.txt` and `dockers/secrets/globus_key.txt`.  Next, we need to create a 
self-signed cert/key pair, also in the `secrets` directory.  This will be for our web service, which will have the
domain `funcx.org` within the Docker network.   
```
openssl req -x509 -newkey rsa:4096 -keyout web-key.pem -out web-cert.pem -nodes    
```  
This will prompt for a bunch of information, none of which matters, except that you set the `Common Name` to
`funcx.org`.

**WARNING**: 
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
