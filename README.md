# FuncX Web Service
This is the client interface to FuncX

# How to locally test
First build the docker image
```shell script
docker build -t funcx_web_service:develop .
```

Run stand-alone with docker 
```shell script
docker run --rm -it -p 8080:5000 \
  --mount "type=bind,source=$PWD/conf,destination=/conf" \
  -e APP_CONFIG_FILE=/conf/app.conf \
  funcx_web_service:develop
```
