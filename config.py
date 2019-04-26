import psycopg2.extras
import globus_sdk
import psycopg2
import os



import parsl
from parsl.app.app import python_app

from parsl.launchers import SingleNodeLauncher
from parsl.channels import SSHInteractiveLoginChannel, LocalChannel
from parsl.providers import CobaltProvider, LocalProvider
from parsl.config import Config
from parsl.executors import HighThroughputExecutor


GLOBUS_KEY = os.environ.get('globus_key')
GLOBUS_CLIENT = os.environ.get('globus_client')

SECRET_KEY = os.environ.get('secret_key')

DB_HOST = os.environ.get('db_host')
DB_USER = os.environ.get('db_user')
DB_NAME = os.environ.get('db_name')
DB_PASSWORD = os.environ.get('db_password')

_prod = True

#cooley_config = Config(
#    executors=[
#        HighThroughputExecutor(
#            label='cooley_htex_remote',
#            max_workers=1,
#            address="3.88.81.131",        # Address of AWS host
#            interchange_address="cooleylogin2.alcf.anl.gov",  # Address at which workers can reach the ix
#            interchange_port_range=(51000,52000),          # Specify accessible ports
#            # worker_debug=True,            # Be careful with this one, dumps a 1GB/few minutes
#            provider=CobaltProvider(
#                #'sandyb',
#                channel=SSHInteractiveLoginChannel(
#                    hostname='cooleylogin2.alcf.anl.gov',
#                    username='rchard',
#                    script_dir="/home/rchard/parsl_scripts/"
#                ),
#                queue="pubnet-debug",
#                launcher=SingleNodeLauncher(),
#                account='DLHub',
#                walltime="1:30:00",
#                init_blocks=1,
#                min_blocks=1,
#                max_blocks=1,
#                nodes_per_block=1,
#                #parallelism=0.5,
#                worker_init="source /home/rchard/setup/remote_parsl.sh"
#            )
#        )
#    ]
#)



config_params = {'username': 'tskluzac'}
config_params = {'username': 'rchard'}

#cooley_config = Config(
#    executors=[
#        HighThroughputExecutor(
#            label='cooley_htex_remote',
#            max_workers=1,
#            address="3.88.81.131",        # Address of AWS host
#            interchange_address="cooleylogin2.alcf.anl.gov",  # Address at which workers can reach the ix
#            interchange_port_range=(51000,52000),          # Specify accessible ports
#            # worker_debug=True,            # Be careful with this one, dumps a 1GB/few minutes
#            provider=CobaltProvider(
#                #'sandyb',
#                channel=SSHInteractiveLoginChannel(
#                    hostname='cooleylogin2.alcf.anl.gov',
#                    username=config_params['username'],
#                    script_dir="/home/{}/parsl_scripts/".format(config_params['username'])
#                ),
#                queue="pubnet-debug",
#                launcher=SingleNodeLauncher(),
#                account='DLHub',
#                walltime="1:30:00",
#                init_blocks=1,
#                min_blocks=1,
#                max_blocks=1,
#                nodes_per_block=1,
#                #parallelism=0.5,
#                worker_init="source /home/{}/setup/remote_parsl.sh".format(config_params['username'])
#            )
#        )
#    ]
#)
#

#parsl.load(cooley_config)

#@python_app
#def test_app():
#    import os
#    with open('my-remote-test.txt', 'w') as f:
#        f.write('test')
#    return 'finished'

#print('testing')
#x = test_app()
#x.result()

config = Config(
    executors=[
        HighThroughputExecutor(
            # poll_period=10,
            label="htex_local",
            worker_debug=True,
            worker_mode="singularity_reuse",
            # worker_mode="singularity_single_use",
            # worker_mode="no_container",
            # We always want the container to be in the home dir.
            container_image=os.path.expanduser("~/sing-run/sing-run.simg"),
            cores_per_worker=1,
            #max_workers=8,
            max_workers=1,
            provider=LocalProvider(
                channel=LocalChannel(),
                init_blocks=1,
                max_blocks=1,
                # max_workers=1,
                # tasks_per_node=1,  # For HighThroughputExecutor, this option should in most cases be 1
                launcher=SingleNodeLauncher(),
            ),
        )
    ],
    #run_dir="/home/ubuntu/parsl/parsl/tests/manual_tests/runinfo/",
    strategy=None,
)

cooley_config = config

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



