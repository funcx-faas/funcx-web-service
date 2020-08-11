#!/bin/sh
mkdir instance
exec gunicorn -b :5000 --workers=5 --threads=1 --timeout 120 --access-logfile - --error-logfile - "funcx_web_service:create_app()"
