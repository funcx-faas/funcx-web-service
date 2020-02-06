import os
import sys
import json
import redis
import uuid
import psycopg2
import psycopg2.extras


def get_endpoint_info():
    """Connect to redis and get endpoint info"""
    REDIS_HOST = os.environ.get('redis_host')
    REDIS_PORT = os.environ.get('redis_port')
    rc = redis.StrictRedis(REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    redis_data = []

    for key in rc.keys('ep_status_*'):
        try:
            print("Getting key {}".format(key))
            endpoint_id = key.split('ep_status_')[1]
            try:
                uuid.UUID(str(endpoint_id))
            except ValueError:
                print('skipping ep:', key)
                continue

            items = rc.lrange(key, 0, 0)
            if items:
                last = json.loads(items[0])
            else:
                continue
            ep_id = key.split('_')[2]
            ep_meta = rc.hgetall('endpoint:{}'.format(ep_id))
            lat, lon = ep_meta['loc'].split(',')
            current = ep_meta
            current['endpoint_id'] = endpoint_id
            current['core_hours'] = last['total_core_hrs']
            current['latitude'] = lat
            current['longitude'] = lon
            if 'hostname' not in current:
                current['hostname'] = None
            redis_data.append(current)

        except Exception as e:
            print(f"Failed to parse for key {key}")
            print(f"Error : {e}")

    return redis_data


def store_data(ep_data, conn, cur):
    """Insert the info into the usage table

    data struct:
    {'ip': '140.221.68.107', 'hostname': 'cooleylogin1.cooley.pub.alcf.anl.gov',
    'city': 'New York City', 'region': 'New York', 'country': 'US', 'loc': '40.7143,-74.0060',
    'org': 'AS683 Argonne National Lab', 'postal': '10004', 'timezone': 'America/New_York',
    'readme': 'https://ipinfo.io/missingauth', 'core_hours': 108.97,
    'latitude': '40.7143', 'longitude': '-74.0060'}

    """
    for data in ep_data:
        query = "update sites set latitude = %s, longitude = %s, ip_addr = %s, city = %s, region = %s, country = %s, " \
                "zipcode = %s, hostname = %s, org = %s, core_hours = %s where endpoint_uuid = %s "
        cur.execute(query, (data['latitude'], data['longitude'], data['ip'], data['city'], data['region'],
                            data['country'], data['postal'], data['hostname'], data['org'], data['core_hours'],
                            data['endpoint_id']))

        conn.commit()


def get_info():
    """Extract usage data from the database and redis then store it in the database"""
    DB_HOST = os.environ.get('db_host')
    DB_USER = os.environ.get('db_user')
    DB_NAME = os.environ.get('db_name')
    DB_PASSWORD = os.environ.get('db_password')

    con_str = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST}"

    conn = psycopg2.connect(con_str)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    data = get_endpoint_info()

    store_data(data, conn, cur)
    print('done')


if __name__ == '__main__':
    get_info()
