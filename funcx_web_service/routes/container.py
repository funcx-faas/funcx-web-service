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

    try:
        container_rec = Container(
            author=user.id,
            name=build_spec["name"],
            description=build_spec.get("description", None),
            container_uuid=str(uuid.uuid4()),
        )

        container_rec.images = [
            ContainerImage(
                type="docker",
                location="pending",
                build_status=ContainerImage.BuildStates.submitted,
            )
        ]

        container_rec.save_to_db()

        if app.extensions["ContainerService"]:
            app.extensions["ContainerService"].submit_build(
                container_rec.container_uuid, build_spec
            )
        else:
            raise InternalError("Container building not available")

        app.logger.info(
            f"Container submitted for build: {container_rec.container_uuid}"
        )
        return jsonify({"container_id": container_rec.container_uuid})

    except Exception as e:
        raise InternalError(f"error adding container - {e}")


@container_api.route("/containers/build/<container_id>", methods=["GET"])
@authenticated
def container_build_status(user: User, container_id):
    container = Container.find_by_uuid_and_type(container_id, "docker")
    if container and len(container.images) == 1:
        return jsonify({"status": container.images[0].build_status.name})
    else:
        raise ContainerNotFound(container_id)


@container_api.route("/containers/<container_id>/status", methods=["PUT"])
def update_container_build_status(container_id):
    def _parse_registry(location_url):
        if location_url == "https://index.docker.io/v1/":
            return "docker.io"
        else:
            return "unknown"

    build_spec = request.json
    container = Container.find_by_uuid_and_type(container_id, "docker")
    if container and len(container.images) == 1:

        docker_rec = container.images[0]
        docker_rec.build_status = build_spec["build_status"]
        if build_spec["build_status"] == ContainerImage.BuildStates.ready.name:
            registry = _parse_registry(build_spec["registry_url"])
            organization = build_spec["registry_user"]
            repository = build_spec["registry_repository"]
            docker_rec.location = f"{registry}/{organization}/{repository}:latest"

            docker_rec.build_stderr = build_spec["repo2docker_stderr"]

        container.save_to_db()
        return jsonify({"status": container.images[0].build_status.name})
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
        )
        container_rec.images = [
            ContainerImage(
                type=post_req["type"],
                location=post_req["location"],
                build_status=ContainerImage.BuildStates.provided,
            )
        ]

        container_rec.save_to_db()

        app.logger.info(f"Created container: {container_rec.container_uuid}")
        return jsonify({"container_id": container_rec.container_uuid})
    except KeyError as e:
        raise RequestKeyError(str(e))

    except Exception as e:
        raise InternalError(f"error adding container - {e}")
