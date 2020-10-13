from flask_migrate import Migrate

from funcx_web_service import create_app
from funcx_web_service.models import db

app = create_app()
db.init_app(app)

migrate = Migrate(app, db)

if __name__ == '__main__':
    app.run("0.0.0.0", port=5000)
