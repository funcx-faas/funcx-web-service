# FuncX Web Service
This is the client interface to FuncX

## How to build docker image
First build the docker image
```shell script
docker build -t funcx_web_service:develop .
```

## How to Test With Kubernetes
You can create all of the required infrstructure for funcX web service and
run it on your host for debugging.

1. Deploy the [helm chart](https://github.com/funcx-faas/helm-chart)
2. Set up your local app config with the following values:
    ```python
    DB_NAME = "public"
    DB_USER = "funcx"
    DB_PASSWORD = "leftfoot1"
    DB_HOST = "localhost"

    REDIS_PORT = 6379
    REDIS_HOST = "localhost"
    ```
3. Forward the postgres pod ports to your host. This command will not return so
start it in another shell.
    ```shell script
    kubectl port-forward funcx-postgresql-0 5432:5432
    ```
4. Forward the Redis master pod ports to your host. This command will not
return so  start it in another shell.
    ```shell script
    kubectl port-forward funcx-redis-master-0 6379:6379
    ```
5. Launch the flask app:
    ```shell script
    APP_CONFIG_FILE=../conf/app.conf PYTHONPATH=. python funcx_web_service/application.py
    ```
6. Obtain a JWT to authenticate requests to the REST server
   ```shell script
    python integration_tests/get_valid_token.py
    ```
7. Use the postman tests in `integration_tests/funcX.postman_collection.json`
with the `host` variable set to `localhost:5000` and the `access_token` set
to your JWT.

