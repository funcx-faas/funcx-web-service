from datetime import datetime

from sqlalchemy import DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from funcx_web_service.models import db


class Container(db.Model):
    __tablename__ = 'containers'
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(Integer, ForeignKey("users.id"))
    container_uuid = db.Column(db.String(67))
    name = db.Column(db.String(1024))
    description = db.Column(db.Text)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    modified_at = db.Column(DateTime, default=datetime.utcnow)

    images = relationship("ContainerImage")
    functions = relationship("FunctionContainer")
    user = relationship("User", back_populates="containers")

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    @classmethod
    def find_by_uuid(cls, uuid):
        try:
            return cls.query.filter_by(container_uuid=uuid).first()
        except NoResultFound:
            return None

    @classmethod
    def find_by_uuid_and_type(cls, uuid, type):
        try:
            return cls.query.filter_by(container_uuid=uuid).join(ContainerImage).filter_by(type=type).first()
        except NoResultFound:
            return None

    def to_json(self):
        result = {
            'container_uuid': self.container_uuid,
            'name': self.name
        }

        if self.images and len(self.images) == 1:
            result['type'] = self.images[0].type
            result['location'] = self.images[0].location

        return result


class ContainerImage(db.Model):
    __tablename__ = "container_images"
    id = db.Column(db.Integer, primary_key=True)
    container_id = db.Column(Integer, ForeignKey('containers.id'))
    type = db.Column(db.String(256))
    location = db.Column(db.String(1024))
    created_at = db.Column(DateTime, default=datetime.utcnow)
    modified_at = db.Column(DateTime, default=datetime.utcnow)
