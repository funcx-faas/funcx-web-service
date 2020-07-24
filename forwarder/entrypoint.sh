pip install -q -e .
[ -d "/funcx" ] && pip install -q -e /funcx
python3 forwarder/service.py -a forwarder -r mockredis --debug