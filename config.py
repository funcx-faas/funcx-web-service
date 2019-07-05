import psycopg2.extras
import globus_sdk
import psycopg2
import redis
import os

GLOBUS_KEY = os.environ.get('globus_key')
GLOBUS_CLIENT = os.environ.get('globus_client')

SECRET_KEY = os.environ.get('secret_key')

DB_HOST = os.environ.get('db_host')
DB_USER = os.environ.get('db_user')
DB_NAME = os.environ.get('db_name')
DB_PASSWORD = os.environ.get('db_password')

REDIS_PORT = os.environ.get('redis_port')
REDIS_HOST = os.environ.get('redis_host')

_prod = True


def _get_db_connection():
    """
    Establish a database connection
    """
    con_str = "dbname={dbname} user={dbuser} password={dbpass} host={dbhost}".format(dbname=DB_NAME, dbuser=DB_USER,
                                                                                     dbpass=DB_PASSWORD, dbhost=DB_HOST)

    conn = psycopg2.connect(con_str)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    return conn, cur


def _load_funcx_client():
    """
    Create an AuthClient for the portal
    """
    print(GLOBUS_CLIENT)
    if _prod:
        app = globus_sdk.ConfidentialAppAuthClient(GLOBUS_CLIENT,
                                                   GLOBUS_KEY)
    else:
        app = globus_sdk.ConfidentialAppAuthClient('', '')
    return app


def _get_redis_client():
    """Return a redis client

    Returns
    -------
    redis.StrictRedis
        A client for redis
    """
    try:
        redisClient = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        return redisClient
    except Exception as e:
        print(e)

