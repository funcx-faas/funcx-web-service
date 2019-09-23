import os
import time
import redis

from threading import Thread, Event
from routes.funcx import funcx_api
from routes.automate import automate_api
from routes.auth import auth_api
from gui.routes import guiapi
from logging.config import dictConfig

from flask import current_app as app, Flask, render_template, request, g, copy_current_request_context
from flask_socketio import SocketIO


dictConfig({
        'version': 1,
        'formatters': {'default': {
                    'format': '%(module)s:%(lineno)d [%(levelname)s]: %(message)s',
                }},
        'handlers': {'wsgi': {
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://flask.logging.wsgi_errors_stream',
                    'formatter': 'default'
                }},
        'root': {
                    'level': 'DEBUG',
                    'handlers': ['wsgi']
                }
    })


application = Flask(__name__, template_folder="gui/templates", static_folder="gui/static")
application.config.from_object(os.environ['APP_SETTINGS'])

# Include the API blueprint
application.register_blueprint(funcx_api, url_prefix="/api/v1")
application.register_blueprint(automate_api, url_prefix="/automate")
application.register_blueprint(auth_api)
application.register_blueprint(guiapi)

io = SocketIO(application)


@io.on('connect', namespace='/ws_core_hours')
def ws_conn():
    app.logger.debug('Client connected!')

    @copy_current_request_context
    def update_counter():
        """
        Emit the core hour count
        """
        if 'redis_client' not in g:
            g.redis_client = redis.Redis(
                host=app.config['REDIS_HOST'],
                port=app.config['REDIS_PORT'])

        while True:
            c = round(float(g.redis_client.get('funcx_worldwide_counter')), 2)
            io.emit('msg', {'count': c}, namespace='/ws_core_hours')
            time.sleep(5)

    if 'counter_thread' not in g:
        g.counter_thread = Thread()

    if not g.counter_thread.isAlive():
        g.counter_thread = Thread(target=update_counter).start()


if __name__ == '__main__':
    io.run(application, "0.0.0.0", port=8080)
