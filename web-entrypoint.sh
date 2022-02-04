#!/bin/sh
FLASK_APP=funcx_web_service/application.py flask db upgrade
uwsgi --ini uwsgi.ini --processes 4