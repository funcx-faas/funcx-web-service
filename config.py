import os
basedir = os.path.abspath(os.path.dirname(__file__))


def read_file_secret(name):
    if not os.path.exists(f"/run/secrets/{name}"):
        return ""
    with open(f"/run/secrets/{name}") as r:
        return r.read().strip()


class Config(object):
    DEBUG = False
    TESTING = False
    SESSION_TYPE = 'filesystem'

    GLOBUS_KEY = os.environ.get('globus_key')
    GLOBUS_CLIENT = os.environ.get('globus_client')

    SECRET_KEY = os.environ.get('secret_key')

    DB_HOST = os.environ.get('db_host')
    DB_USER = os.environ.get('db_user')
    DB_NAME = os.environ.get('db_name')
    DB_PASSWORD = os.environ.get('db_password')
    FORWARDER_IP = os.environ.get('forwarder_ip')

    REDIS_PORT = os.environ.get('redis_port')
    REDIS_HOST = os.environ.get('redis_host')

    SERIALIZATION_ADDR = os.environ.get('serialization_addr')
    SERIALIZATION_PORT = os.environ.get('serialization_port')

    HOSTNAME = os.environ.get('hostname')


class ProductionConfig(Config):
    DEBUG = False


class StagingConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class DevelopmentConfig(Config):
    DEVELOPMENT = True
    DEBUG = True


class TestingConfig(Config):
    TESTING = True


class LocalDevelopmentConfig(DevelopmentConfig):
    GLOBUS_CLIENT = read_file_secret("globus_client")
    GLOBUS_KEY = read_file_secret("globus_key")

    DB_HOST = "mockrds"
    DB_USER = "funcx"
    DB_NAME = "funcx"
    DB_PASSWORD = "local-dev-password"

    FORWARDER_IP = "forwarder"

    REDIS_HOST = "mockredis"
    REDIS_PORT = "6379"

    SERIALIZATION_ADDR = "serializer"
    SERIALIZATION_PORT = "8080"

    HOSTNAME = "localhost:8080"