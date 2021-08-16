#!/bin/sh
FLASK_APP=funcx_web_service/application.py flask db upgrade
/uwsgi-venv/bin/uwsgi --ini uwsgi.ini
