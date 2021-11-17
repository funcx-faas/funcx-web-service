from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def load_all_models():
    # deferred import of the necessary model code
    from . import auth_groups, container, function, user  # noqa: F401
