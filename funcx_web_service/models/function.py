from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from funcx_web_service.models import db
from funcx_web_service.models.endpoint import restricted_endpoint_table


class Function(db.Model):
    __tablename__ = "functions"
    __table_args__ = (
        db.UniqueConstraint("function_uuid", name="unique_function_uuid"),
    )

    id = db.Column(Integer, nullable=False, primary_key=True, autoincrement=True)
    user_id = db.Column(Integer, ForeignKey("users.id"))
    name = db.Column(String(1024))
    description = db.Column(Text)
    status = db.Column(String(1024))
    function_name = db.Column(String(1024))
    function_uuid = db.Column(String(38))
    function_source_code = db.Column(Text)
    timestamp = db.Column(DateTime, default=datetime.utcnow)
    entry_point = db.Column(String(38))
    modified_at = db.Column(DateTime, default=datetime.utcnow)
    deleted = db.Column(db.Boolean, default=False)
    public = db.Column(db.Boolean, default=False)

    container = relationship(
        "FunctionContainer", uselist=False, back_populates="function"
    )
    auth_groups = relationship("FunctionAuthGroup")

    tasks = relationship("DBTask")

    restricted_endpoints = relationship(
        "Endpoint",
        secondary=restricted_endpoint_table,
        back_populates="restricted_functions",
    )

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
    __tablename__ = "function_containers"
    id = db.Column(Integer, primary_key=True)
    container_id = db.Column(Integer, ForeignKey("containers.id"))
    function_id = db.Column(Integer, ForeignKey("functions.id"))
    created_at = db.Column(DateTime, default=datetime.utcnow)
    modified_at = db.Column(DateTime, default=datetime.utcnow)

    function = relationship("Function", back_populates="container")
    container = relationship("Container", back_populates="functions")


class FunctionAuthGroup(db.Model):
    __tablename__ = "function_auth_groups"
    id = db.Column(Integer, primary_key=True)
    group_id = db.Column(String(38))
    function_id = db.Column(Integer, ForeignKey("functions.id"))
    function = relationship("Function", back_populates="auth_groups")

    @classmethod
    def find_by_function_id(cls, function_id):
        return cls.query.filter_by(function_id=function_id).all()
