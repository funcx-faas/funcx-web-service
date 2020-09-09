from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from funcx_web_service.models import db


class User(db.Model):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(256))
    globus_identity = Column(String(256))
    created_at = db.Column(DateTime, default=datetime.utcnow)
    namespace = Column(String(1024))
    deleted = Column(Boolean, default=False)

    functions = relationship("Function")

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    @classmethod
    def find_by_username(cls, username):
        try:
            return cls.query.filter_by(username=username).first()
        except NoResultFound:
            return None
