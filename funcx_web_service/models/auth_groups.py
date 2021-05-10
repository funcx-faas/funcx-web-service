from sqlalchemy import Column, Integer, String
from sqlalchemy.orm.exc import NoResultFound

from funcx_web_service.models import db


class AuthGroup(db.Model):
    __tablename__ = 'auth_groups'
    id = Column(Integer, primary_key=True)
    group_id = Column(String(67))
    endpoint_id = Column(String(67))

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    @classmethod
    def find_by_uuid(cls, uuid):
        try:
            return cls.query.filter_by(group_id=uuid).first()
        except NoResultFound:
            return None

    @classmethod
    def find_by_endpoint_uuid(cls, endpoint_uuid):
        return cls.query.filter_by(endpoint_id=endpoint_uuid).all()
