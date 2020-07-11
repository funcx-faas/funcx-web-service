First build the funcX web base image:
```bash
cd dockers/base
docker build -t funcx-web-base .
```
Then, from the main `funcx-web-service` directory, you can run:
```
docker-compose up
```
If any requirements in the API, Forwarder, or Serializer change, make sure to run: 
```
pip freeze > dockers/base/all-requirements.txt
docker-compose build
```