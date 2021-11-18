import uuid

from flask import Blueprint
from flask import current_app as app
from flask import jsonify, request
from funcx_common.response_errors import InternalError, RequestKeyError

from funcx_web_service.authentication.auth import authenticated

from ..models.container import Container, ContainerImage
from ..models.user import User

container_api = Blueprint("container_routes", __name__)


@container_api.route("/containers/<container_id>/<container_type>", methods=["GET"])
@authenticated
def get_cont(user: User, container_id, container_type):
    """Get the details of a container.

    Parameters
    ----------
    user : User
        The primary identity of the user
    container_id : str
        The id of the container
    container_type : str
        The type of containers to return: Docker, Singularity, Shifter, etc.

    Returns
    -------
    dict
        A dictionary of container details
    """

    app.logger.info(f"Getting container details: {container_id}")
    container = Container.find_by_uuid_and_type(container_id, container_type)
    app.logger.info(f"Got container: {container}")
    return jsonify({"container": container.to_json()})


@container_api.route("/containers", methods=["POST"])
@authenticated
def reg_container(user: User):
    """Register a new container.

    Parameters
    ----------
    user : User
        The primary identity of the user

    JSON Body
    ---------
        name: Str
        description: Str
        type: The type of containers that will be used (Singularity, Shifter, Docker)
        location:  The location of the container (e.g., its docker url).

    Returns
    -------
    dict
        A dictionary of container details including its uuid
    """

    app.logger.debug("Creating container.")
    post_req = request.json

    try:
        container_rec = Container(
            author=user.id,
            name=post_req["name"],
            description=None
            if not post_req["description"]
            else post_req["description"],
            container_uuid=str(uuid.uuid4()),
        )
        container_rec.images = [
            ContainerImage(type=post_req["type"], location=post_req["location"])
        ]

        container_rec.save_to_db()

        app.logger.info(f"Created container: {container_rec.container_uuid}")
        return jsonify({"container_id": container_rec.container_uuid})
    except KeyError as e:
        raise RequestKeyError(str(e))

    except Exception as e:
        raise InternalError(f"error adding container - {e}")
