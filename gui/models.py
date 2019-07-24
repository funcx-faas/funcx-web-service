from datetime import datetime
import uuid
from funcx_app import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(20), nullable=False)
# functions = db.relationship('Function', backref='author', lazy=True)

class Function(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(), nullable=False, default=str(uuid.uuid4()))
    title = db.Column(db.String(20), nullable=False)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    date_edited = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    language = db.Column(db.String(20), nullable=False, default="Plain Text")
    content = db.Column(db.Text, nullable=False, default="")
# user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
