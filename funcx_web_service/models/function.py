from datetime import datetime

from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from funcx_web_service.models import db
from sqlalchemy import Column, ForeignKey, DateTime, Integer, String, Text


class Function(db.Model):
    __tablename__ = 'functions'
    id = Column(Integer, nullable=False, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(1024))
    description = Column(Text)
    status = Column(String(1024))
    function_name = Column(String(1024))
    function_uuid = Column(String(38))
    function_source_code = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    entry_point = Column(String(38))
    modified_at = Column(DateTime, default=datetime.utcnow)
    deleted = Column(db.Boolean, default=False)
    public = Column(db.Boolean, default=False)

    container = relationship("FunctionContainer", uselist=False, back_populates="function")
    auth_groups = relationship("FunctionAuthGroup")
    user = relationship("User", back_populates="functions")

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    @classmethod
    def find_by_uuid(cls, uuid):
        try:
            return cls.query.filter_by(function_uuid=uuid).first()
        except NoResultFound:
            return None


class FunctionContainer(db.Model):
    __tablename__ = 'function_containers'
    id = Column(Integer, primary_key=True)
    container_id = Column(Integer, ForeignKey('containers.id'))
    function_id = Column(Integer, ForeignKey('functions.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    modified_at = Column(DateTime, default=datetime.utcnow)

    function = relationship("Function", back_populates='container')
    container = relationship("Container", back_populates='functions')


class FunctionAuthGroup(db.Model):
    __tablename__ = "function_auth_groups"
    id = Column(Integer, primary_key=True)
    group_id = Column(Integer, ForeignKey("auth_groups.id"))
    function_id = Column(Integer, ForeignKey('functions.id'))

    function = relationship("Function", back_populates='auth_groups')
    group = relationship("AuthGroup", back_populates='functions')
