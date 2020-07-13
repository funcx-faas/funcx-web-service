pip install -q -e .
python3 forwarder/service.py -a forwarder -r mockredis --debug
#tail -f /dev/null