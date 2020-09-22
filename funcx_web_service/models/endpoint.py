from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from funcx_web_service.models import db


class Endpoint(db.Model):
    __tablename__ = 'sites'
    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    description = Column(String(256))
    user_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(10))
    endpoint_name = Column(String(256))
    endpoint_uuid = Column(String(38))
    public = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)
    ip_addr = Column(String(15))
    city = Column(String(256))
    region = Column(String(256))
    country = Column(String(256))
    zipcode = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)
    core_hours = Column(Float, default=0)
    hostname = Column(String(256))
    org = Column(String(256))
    restricted = Column(Boolean, default=False)

    created_at = db.Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="endpoints")

    # groups integer[] DEFAULT '{1}'::integer[]

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    @classmethod
    def find_by_uuid(cls, uuid):
        try:
            return cls.query.filter_by(endpoint_uuid=uuid).first()
        except NoResultFound:
            return None
