[![NSF-2004894](https://img.shields.io/badge/NSF-2004894-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=2004894)
[![NSF-2004932](https://img.shields.io/badge/NSF-2004932-blue.svg)](https://nsf.gov/awardsearch/showAward?AWD_ID=2004932)

# How to locally test
First build the funcX web base image:
```bash
cd dockers/base
docker build -t funcx-web-base .
```
Next, we need to ensure that we have the correct directory structure.  You will need to move files around so that your
tree has this:
```
funcx-faas/
    docker-compose.yml
    funcX/
    funcx-web-service/
```
It is important that the main `docker-compose.yml` file and the two repos are at the same level. (This is due to the
way in which the build context is sent to the docker daemon, and other solutions are clunky.)
## Secrets
#### **WARNING**: make sure to have the `dockers/secrets` directory in your `.gitignore` if it is not already.  
You'll need a few secrets for the app to work properly.  First, let's do the Globus secrets: the funcX Globus Confidential Client ID and Key.
Place them in `dockers/secrets/globus_client.txt` and `dockers/secrets/globus_key.txt`.  Next, we need to create a 
self-signed cert/key pair, also in the `secrets` directory.  This will be for our web service, which will have the
domain `funcx.org` within the Docker network.   
```
cd funcx-web-service/dockers/secrets
openssl req -x509 -newkey rsa:4096 -keyout web-key.pem -out web-cert.pem -nodes    
```  
This will prompt for a bunch of information, none of which matters, except that you set the `Common Name` to
`funcx.org`.  Next, for convenience, let's place your funcx credentials and config in the endpoint container. 
If you do not do this, you will need to change the endpoint `entrypoint.sh`, and manually log in every time.  This
should be done from within the `dockers/secrets` directory.  
```
mkdir funcx-credentials
cp ~/.funcx/credentials/funcx_sdk_tokens.json funcx-credentials/
cp ~/.funcx/config.py funcx-config.py 
```  
## Testing your code
### Setting `funcX` sdk path

In order to test changes to the `funcX` client/sdk as well as the web, you will need to set the path to your `funcX`
install in `docker-compose.yml`.  Find the top-level `volumes` key (near the bottom of the file).  Set the `device` key
to point to your local `funcX` repo (for me, it was a sibling of the `funcx-web-service` repo).    
```yaml
volumes:
  funcx_install:
    driver: local
    driver_opts:
      type: none
      device: ./funcX
      o: bind
```  
If you would like to use a master version of `funcX` from PyPI, you can avoid doing this.  You must also then remove
the mount lines for the `funcx_install` volume, which are keys under each service, and look like this:
```yaml
    volumes:
      - funcx_install:/funcx
```
The three services that look for this are the `funcx_web_service`, the `serializer`, and the `forwarder`.  

### Running

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

**Note:** it would/will be possible to run the notebook from your laptop instead, but for a variety of reasons, it is
better to run it from within the container network.  First, for library consistency.  We want the notebook to use the
same library versions as exist in the containers, and so the easiest way to do that is to just run it in a
container as well.  Second, the easy way of making the web server's certs causes some issues with the `requests`
library when connecting from the host machine (the cert claims to be for `funcx.org`, which the host knows isn't true).

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
