import os
import redis
import psycopg2
import psycopg2.extras


def rds_usage(conn, cur):
    """Connect to the database and pull out usage info"""
    db_data = {}
    # Number of users
    query = "select count(*) from users"
    cur.execute(query)
    row = cur.fetchone()
    if row and 'count' in row:
        db_data['users'] = row['count']

    # Number of endpoints
    query = "select count(*) from sites"
    cur.execute(query)
    row = cur.fetchone()
    if row and 'count' in row:
        db_data['endpoints'] = row['count']

    # Number of functions
    query = 'select count(*) from functions'
    cur.execute(query)
    row = cur.fetchone()
    if row and 'count' in row:
        db_data['functions'] = row['count']

    # Active endpoints, users, functions in last day
    query = "select count(distinct function_id) as functions, count(distinct user_id) as users, count(distinct " \
            "endpoint_id) as endpoints from tasks WHERE created_at > current_date - interval '1' day; "
    cur.execute(query)
    row = cur.fetchone()
    if row:
        db_data['endpoints_day'] = row['endpoints']
        db_data['functions_day'] = row['functions']
        db_data['users_day'] = row['users']

    # Active endpoints, users, functions in last week
    query = "select count(distinct function_id) as functions, count(distinct user_id) as users, count(distinct " \
            "endpoint_id) as endpoints from tasks WHERE created_at > current_date - interval '7' day; "
    cur.execute(query)
    row = cur.fetchone()
    if row:
        db_data['endpoints_week'] = row['endpoints']
        db_data['functions_week'] = row['functions']
        db_data['users_week'] = row['users']

    # Active things this month
    query = "select count(distinct function_id) as functions, count(distinct user_id) as users, count(distinct " \
            "endpoint_id) as endpoints from tasks WHERE created_at >= date_trunc('month', CURRENT_DATE); "
    cur.execute(query)
    row = cur.fetchone()
    if row:
        db_data['endpoints_month'] = row['endpoints']
        db_data['functions_month'] = row['functions']
        db_data['users_month'] = row['users']

    return db_data


def redis_usage():
    """Connect to redis and get counters"""
    REDIS_HOST = os.environ.get('redis_host')
    REDIS_PORT = os.environ.get('redis_port')
    rc = redis.StrictRedis(REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    redis_data = {}
    # Total core hours
    redis_data['core_hours'] = rc.get('funcx_worldwide_counter')
    # Total function invocations
    redis_data['invocations'] = rc.get('funcx_invocation_counter')
    return redis_data


def store_data(data, conn, cur):
    """Insert the info into the usage table

    DB STRUCTURE:
      total_functions int,
      total_endpoints int,
      total_users int,
      total_core_hours float,
      total_invocations int,
      functions_day int,
      functions_week int,
      functions_month int,
      endpoints_day int,
      endpoints_week int,
      endpoints_month int,
      users_day int,
      users_week int,
      users_month int
    """
    query = "insert into usage_info (total_functions, total_endpoints, total_users, total_core_hours, " \
            "total_invocations, functions_day, functions_week, functions_month, endpoints_day, " \
            "endpoints_week, endpoints_month, users_day, users_week, users_month) values (%s, %s, %s, %s, " \
            "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);"
    cur.execute(query, (data['functions'], data['endpoints'], data['users'], float(data['core_hours']),
                        int(data['invocations']), data['functions_day'], data['functions_week'], data['functions_month'],
                        data['endpoints_day'], data['endpoints_week'], data['endpoints_month'],
                        data['users_day'], data['users_week'], data['users_month']))
    conn.commit()


def record_usage():
    """Extract usage data from the database and redis then store it in the database"""
    DB_HOST = os.environ.get('db_host')
    DB_USER = os.environ.get('db_user')
    DB_NAME = os.environ.get('db_name')
    DB_PASSWORD = os.environ.get('db_password')

    con_str = f"dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD} host={DB_HOST}"

    conn = psycopg2.connect(con_str)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    data = rds_usage(conn, cur)
    redis_data = redis_usage()

    # Combine them together
    data.update(redis_data)
    print(data)

    store_data(data, conn, cur)
    print('done')


if __name__ == '__main__':
    record_usage()
