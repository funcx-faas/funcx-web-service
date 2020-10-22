from datetime import datetime

from sqlalchemy import Integer, String, Boolean, DateTime, Float, ForeignKey, and_
from sqlalchemy.orm import relationship
from sqlalchemy.orm.exc import NoResultFound

from funcx_web_service.models import db
from funcx_web_service.models.user import User

restricted_endpoint_table = db.Table('restricted_endpoint_functions',
                                     db.Column("id", Integer, primary_key=True),
                                     db.Column("endpoint_id", Integer,
                                               ForeignKey("sites.id")),
                                     db.Column("function_id", Integer,
                                               ForeignKey('functions.id')))


class Endpoint(db.Model):
    __tablename__ = 'sites'
    __table_args__ = (
        db.UniqueConstraint('endpoint_uuid', name='unique_endpoint_uuid'),
    )

    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(256))
    description = db.Column(String(256))
    user_id = db.Column(Integer, ForeignKey("users.id"))
    status = db.Column(String(10))
    endpoint_name = db.Column(String(256))
    endpoint_uuid = db.Column(String(38), )
    public = db.Column(Boolean, default=False)
    deleted = db.Column(Boolean, default=False)
    ip_addr = db.Column(String(15))
    city = db.Column(String(256))
    region = db.Column(String(256))
    country = db.Column(String(256))
    zipcode = db.Column(String(10))
    latitude = db.Column(Float)
    longitude = db.Column(Float)
    core_hours = db.Column(Float, default=0)
    hostname = db.Column(String(256))
    org = db.Column(String(256))
    restricted = db.Column(Boolean, default=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="endpoints")
    tasks = relationship("DBTask")

    restricted_functions = db.relationship(
        "Function",
        secondary=restricted_endpoint_table,
        back_populates="restricted_endpoints")

    def save_to_db(self):
        db.session.add(self)
        db.session.commit()

    def delete_whitelist_for_function(self, function):
        conn = db.engine.connect()

        s = restricted_endpoint_table.delete(). \
            where(and_(restricted_endpoint_table.c.endpoint_id == self.id,
                       restricted_endpoint_table.c.function_id == function.id))

        conn.execute(s)

    @classmethod
    def find_by_uuid(cls, uuid):
        try:
            return cls.query.filter_by(endpoint_uuid=uuid).first()
        except NoResultFound:
            return None

    @classmethod
    def delete_endpoint(cls, user: User, endpoint_uuid):
        """Delete a function

        Parameters
        ----------
        user : User
            The primary identity of the user
        endpoint_uuid : str
            The uuid of the endpoint

        Returns
        -------
        str
            The result as a status code integer
                "302" for success and redirect
                "403" for unauthorized
                "404" for a non-existent or previously-deleted endpoint
                "500" for try statement error
        """

        user_id = user.id

        try:
            existing_endpoint = Endpoint.find_by_uuid(endpoint_uuid)
            if existing_endpoint:
                if not existing_endpoint.deleted:
                    if existing_endpoint.user_id == user_id:
                        existing_endpoint.deleted = True
                        existing_endpoint.save_to_db()
                        return 302
                    else:
                        return 403  # Endpoint doesn't belong to user
                else:
                    return 404  # Endpoint is already deleted
            else:
                return 404  # Endpoint not found

        except Exception as e:
            print(e)
            return 500
