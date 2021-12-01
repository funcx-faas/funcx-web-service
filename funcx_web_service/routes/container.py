import uuid

from flask import Blueprint
from flask import current_app as app
from flask import jsonify, request
from funcx_common.response_errors import (
    ContainerNotFound,
    InternalError,
    RequestKeyError,
    RequestMalformed,
)

from funcx_web_service.authentication.auth import authenticated

from ..models.container import Container, ContainerImage
from ..models.user import User

container_api = Blueprint("container_routes", __name__)


@container_api.route("/containers/build", methods=["POST"])
@authenticated
def build_container(user: User):
    build_spec = request.json

    if not build_spec:
        raise RequestMalformed("No container spec found in request")

    if "name" not in build_spec:
        raise RequestKeyError("name")

    apt_spec = build_spec.get("apt", None)
    pip_spec = build_spec.get("pip", None)
    conda_spec = build_spec.get("conda", None)

    try:
        container_rec = Container(
            author=user.id,
            name=build_spec["name"],
            description=build_spec.get("description", None),
            container_uuid=str(uuid.uuid4()),
            build_status="submitted",
        )

        container_rec.save_to_db()

        app.logger.info(
            f"Container submitted for build: {container_rec.container_uuid}"
        )
        return jsonify({"container_id": container_rec.container_uuid})

    except Exception as e:
        raise InternalError(f"error adding container - {e}")


@container_api.route("/containers/build/<container_id>", methods=["GET"])
@authenticated
def container_build_status(user: User, container_id):
    print(f"Get the status of {container_id}")
    container = Container.find_by_uuid(container_id)
    print(container)
    if container:
        return jsonify({"status": container.build_status.name})
    else:
        raise ContainerNotFound(container_id)


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

    if container:
        app.logger.info(f"Got container: {container}")
        return jsonify({"container": container.to_json()})
    else:
        raise ContainerNotFound(container_id)


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
            description=post_req.get("description", None),
            container_uuid=str(uuid.uuid4()),
            build_status=Container.BuildStates.provided,
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
