# How to locally test
First build the funcX web base image:
```bash
cd dockers/base
docker build -t funcx-web-base .
```
## Secrets
#### **WARNING**: make sure to have the `dockers/secrets` directory in your `.gitignore` if it is not already.  
You'll need a few secrets for the app to work properly.  First, let's do the Globus secrets: the funcX Globus Confidential Client ID and Key.
Place them in `dockers/secrets/globus_client.txt` and `dockers/secrets/globus_key.txt`.  Next, we need to create a 
self-signed cert/key pair, also in the `secrets` directory.  This will be for our web service, which will have the
domain `funcx.org` within the Docker network.   
```
openssl req -x509 -newkey rsa:4096 -keyout web-key.pem -out web-cert.pem -nodes    
```  
This will prompt for a bunch of information, none of which matters, except that you set the `Common Name` to
`funcx.org`.  Next, for convenience, let's place your funcx credentials and config in the endpoint container. 
If you do not do this, you will need to change the endpoint `entrypoint.sh`, and manually log in every time. 
```
mkdir dockers/secrets/funcx-credentials
cp ~/.funcx/credentials/funcx_sdk_tokens.json dockers/secrets/funcx-credentials/
cp ~/.funcx/config.py dockers/secrets/funcx-config.py 
```  
## Testing your code
Currently, it is only easy to test changes to the web service.  This will soon be updated to allow testing of new
client code.  

From the main `funcx-web-service` directory, you can run:
```
docker-compose up
```
A lot of logging will be printed out, but you want to find the jupyter starting line that looks like:
```
Or copy and paste one of these URLs:
    http://127.0.0.1:8888/?token=[...]
```
Copy and paste this into your browser, and you will be plunked into your `dockers/endpoints/` directory that is
mounted into the endpoint container.  You can make a jupyter notebook there, which will be saved on the host as well.

### Viewing logs
For now, most service logs are dumped to the console where you ran `docker-compose up`.  Some logs from other processes
however do not appear there.  The spawned forwarder logs are available on your host in `forwarder/forwarder_logs`.  You
can access endpoint worker logs by connecting to the endpoint:
```
docker exec -it funcx-web-service_endpoints_1 sh
cd ~/.funcx/default/worker_logs
```

## Updating requirements
If any requirements in the API, Forwarder, or Serializer change, make sure to update the appropriate requirements
file and then next time: 
```bash
docker-compose up --build
```
