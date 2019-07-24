from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///funcs.db'
app.config['SECRET_KEY'] = 'd67d15bcc528d7fcb2ebd483fcece6db'
db = SQLAlchemy(app)

# from funcx_app import routes
