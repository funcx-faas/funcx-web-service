import json
import time
import uuid

import requests
from flask import Blueprint
from flask import current_app as app
from flask import g, jsonify, request
from funcx_common.redis import FuncxRedisPubSub
from funcx_common.response_errors import (
    ContainerNotFound,
    EndpointAccessForbidden,
    EndpointOutdated,
    EndpointStatsError,
    ForwarderRegistrationError,
    FunctionAccessForbidden,
    InternalError,
    InvalidUUID,
    RequestKeyError,
    RequestMalformed,
    TaskGroupAccessForbidden,
    TaskGroupNotFound,
    TaskNotFound,
    UserNotFound,
)
from redis.client import Redis

from funcx_web_service.authentication.auth import (
    authenticated,
    authenticated_w_uuid,
    authorize_endpoint,
    authorize_function,
)
from funcx_web_service.error_responses import create_error_response
from funcx_web_service.models.tasks import RedisTask, TaskGroup
from funcx_web_service.models.utils import (
    add_ep_whitelist,
    db_invocation_logger,
    delete_ep_whitelist,
    delete_function,
    get_ep_whitelist,
    get_redis_client,
    ingest_endpoint,
    ingest_function,
    register_endpoint,
    resolve_function,
    update_function,
)
from funcx_web_service.version import MIN_SDK_VERSION, VERSION

# Flask
from ..models.container import Container, ContainerImage
from ..models.endpoint import Endpoint
from ..models.function import Function, FunctionAuthGroup, FunctionContainer
from ..models.serializer import deserialize_result, serialize_inputs
from ..models.user import User

funcx_api = Blueprint("routes", __name__)


def get_db_logger():
    if "db_logger" not in g:
        g.db_logger = db_invocation_logger()
    return g.db_logger


def g_redis_client():
    if "redis_client" not in g:
        g.redis_client = get_redis_client()
    return g.redis_client


def g_redis_pubsub():
    if "redis_pubsub" not in g:
        g.redis_pubsub = FuncxRedisPubSub(
            app.config["REDIS_HOST"], port=app.config["REDIS_PORT"]
        )
        g.redis_pubsub.redis_client.ping()
    return g.redis_pubsub


def auth_and_launch(
    user_id,
    function_uuid,
    endpoint_uuid,
    input_data,
    app,
    token,
    task_group_id,
    serialize=None,
):
    """Here we do basic auth for (user, fn, endpoint) and launch the function.

    Parameters
    ==========

    user_id : str
       user id
    function_uuid : str
       function uuid
    endpoint_uuid : str
       endpoint uuid
    input_data : string_buffer
       input payload data
    app : app object
    token : globus token
    serialize : bool
        Whether or not to serialize the input using the serialization service. This is
        used when the input is not already serialized by the SDK.

    Returns:
       JSON response object, containing task_uuid, http_status_code, and success or
       error info
    """

    task_uuid = str(uuid.uuid4())
    try:
        # Check if the user is allowed to access the function
        if not authorize_function(user_id, function_uuid, token):
            raise FunctionAccessForbidden(function_uuid)

        fn_code, fn_entry, container_uuid = resolve_function(user_id, function_uuid)

        # Make sure the user is allowed to use the function on this endpoint
        if not authorize_endpoint(user_id, endpoint_uuid, function_uuid, token):
            raise EndpointAccessForbidden(endpoint_uuid)

        app.logger.info(f"Got function container_uuid :{container_uuid}")

        # We should replace this with container_hdr = ";ctnr={container_uuid}"
        if not container_uuid:
            container_uuid = "RAW"

        rc = g_redis_client()
        task_channel = g_redis_pubsub()

        db_logger = get_db_logger()

        if serialize:
            serialize_res = serialize_inputs(input_data)
            if serialize_res:
                input_data = serialize_res

        # At this point the packed function body and the args are concatable strings
        payload = fn_code + input_data
        task = RedisTask(
            rc,
            task_uuid,
            user_id=user_id,
            function_id=function_uuid,
            container=container_uuid,
            payload=payload,
            task_group_id=task_group_id,
        )

        task_channel.put(endpoint_uuid, task)

        extra_logging = {
            "user_id": user_id,
            "task_id": task_uuid,
            "task_group_id": task_group_id,
            "function_id": function_uuid,
            "endpoint_id": endpoint_uuid,
            "container_id": container_uuid,
            "log_type": "task_transition",
        }
        app.logger.info("received", extra=extra_logging)

        # increment the counter
        rc.incr("funcx_invocation_counter")
        # add an invocation to the database
        # log_invocation(user_id, task_uuid, function_uuid, ep)
        db_logger.log(user_id, task_uuid, function_uuid, endpoint_uuid, deferred=True)

        db_logger.commit()

        return {"status": "Success", "task_uuid": task_uuid, "http_status_code": 200}
    except Exception as e:
        app.logger.exception(e)
        res = create_error_response(e)[0]
        res["task_uuid"] = task_uuid
        return res


@funcx_api.route("/submit", methods=["POST"])
@authenticated
def submit(user: User):
    """Puts the task request(s) into Redis and returns a list of task UUID(s)
    Parameters
    ----------
    user : User
    The primary identity of the user

    POST payload
    ------------
    {
        tasks: []
    }
    Returns
    -------
    json
        The task document
    """

    app.logger.info(f"batch_run invoked by user:{user.username}")

    user_id = user.id

    # Extract the token for endpoint verification
    token_str = request.headers.get("Authorization")
    token = str.replace(str(token_str), "Bearer ", "")

    # Parse out the function info
    tasks = []
    task_group_id = None
    try:
        post_req = request.json
        if "tasks" in post_req:
            # new client is being used
            # TODO: validate that this tasks list is formatted correctly so
            # that more useful errors can be sent back
            tasks = post_req["tasks"]
            task_group_id = post_req.get("task_group_id", str(uuid.uuid4()))
            try:
                # check that task_group_id is a valid UUID
                uuid.UUID(task_group_id)
            except Exception:
                raise InvalidUUID("Invalid task_group_id UUID provided")
        else:
            # old client was used and create a new task
            function_uuid = post_req["func"]
            endpoint = post_req["endpoint"]
            input_data = post_req["payload"]
            tasks.append([function_uuid, endpoint, input_data])
        serialize = post_req.get("serialize", None)
    except KeyError as e:
        # this should raise a 500 because it prevented any tasks from launching
        raise RequestKeyError(str(e))

    rc = g_redis_client()
    task_group = None
    if task_group_id and TaskGroup.exists(rc, task_group_id):
        app.logger.debug(
            f"Task Group {task_group_id} submitted to by user {user_id} "
            "already exists, checking if user is authorized"
        )
        # TODO: This could be cached to minimize lookup cost.
        task_group = TaskGroup(rc, task_group_id)
        if task_group.user_id != user_id:
            raise TaskGroupAccessForbidden(task_group_id)

    # this is a breaking change for old funcx sdk versions
    results = {"response": "batch", "task_group_id": task_group_id, "results": []}

    final_http_status = 200
    success_count = 0
    for task in tasks:
        res = auth_and_launch(
            user_id,
            function_uuid=task[0],
            endpoint_uuid=task[1],
            input_data=task[2],
            app=app,
            token=token,
            task_group_id=task_group_id,
            serialize=serialize,
        )

        if res.get("status", "Failed") == "Success":
            success_count += 1
        else:
            # the response code is a 207 if some tasks failed to submit
            final_http_status = 207

        results["results"].append(res)

    # create a TaskGroup if there are actually tasks with results to wait on and
    # a TaskGroup with the provided ID doesn't already exist
    if success_count > 0 and task_group_id and not task_group:
        app.logger.debug(f"Creating new Task Group {task_group_id} for user {user_id}")
        TaskGroup(rc, task_group_id, user_id)

    return jsonify(results), final_http_status


def get_tasks_from_redis(task_ids, user: User):
    all_tasks = {}

    rc = g_redis_client()
    for task_id in task_ids:
        # Get the task from redis
        if not RedisTask.exists(rc, task_id):
            all_tasks[task_id] = {
                "task_id": task_id,
                "status": "Failed",
                "reason": "Unknown task id",
            }
            continue

        task = RedisTask(rc, task_id)
        if task.user_id != user.id:
            all_tasks[task_id] = {
                "task_id": task_id,
                "status": "Failed",
                "reason": "Unknown task id",
            }
            continue

        task_status = task.status
        task_result = task.result
        task_exception = task.exception
        task_completion_t = task.completion_time
        if task_result or task_exception:
            task.delete()

        all_tasks[task_id] = {
            "task_id": task_id,
            "status": task_status,
            "result": task_result,
            "completion_t": task_completion_t,
            "exception": task_exception,
        }

        # Note: this is for backwards compat, when we can't include a None result and
        # have a non-complete status, we must forgo the result field if task not
        # complete.
        if task_result is None:
            del all_tasks[task_id]["result"]

        # Note: this is for backwards compat, when we can't include a None result and
        # have a non-complete status, we must forgo the result field if task not
        # complete.
        if task_exception is None:
            del all_tasks[task_id]["exception"]
    return all_tasks


def get_task_or_404(rc: Redis, task_id: str) -> RedisTask:
    if not RedisTask.exists(rc, task_id):
        raise TaskNotFound(task_id)
    return RedisTask(rc, task_id)


def authorize_task_or_404(task: RedisTask, user: User):
    if task.user_id != user.id:
        raise TaskNotFound(task.task_id)


# TODO: Old APIs look at "/<task_id>/status" for status and result, when that's changed,
# we should remove this route
@funcx_api.route("/<task_id>/status", methods=["GET"])
@funcx_api.route("/tasks/<task_id>", methods=["GET"])
@authenticated
def status_and_result(user: User, task_id):
    """Check the status of a task.  Return result if available.

    If the query param deserialize=True is passed, then we deserialize the result
    object.

    Parameters
    ----------
    user : User
        The primary identity of the user
    task_id : str
        The task uuid to look up

    Returns
    -------
    json
        The status of the task
    """
    rc = g_redis_client()
    task = get_task_or_404(rc, task_id)
    authorize_task_or_404(task, user)

    task_status = task.status
    task_result = task.result
    task_exception = task.exception
    task_completion_t = task.completion_time
    if task_result or task_exception:
        extra_logging = {
            "user_id": task.user_id,
            "task_id": task_id,
            "task_group_id": task.task_group_id,
            "function_id": task.function_id,
            "endpoint_id": task.endpoint,
            "container_id": task.container,
            "log_type": "task_transition",
        }
        app.logger.info("user_fetched", extra=extra_logging)

        task.delete()

    deserialize = request.args.get("deserialize", False)
    if deserialize and task_result:
        task_result = deserialize_result(task_result)

    # TODO: change client to have better naming conventions
    # these fields like 'status' should be changed to 'task_status', because 'status' is
    # normally used for HTTP codes.
    response = {
        "task_id": task_id,
        "status": task_status,
        "result": task_result,
        "completion_t": task_completion_t,
        "exception": task_exception,
    }

    # Note: this is for backwards compat, when we can't include a None result and have a
    # non-complete status, we must forgo the result field if task not complete.
    if task_result is None:
        del response["result"]

    if task_exception is None:
        del response["exception"]

    return jsonify(response)


@funcx_api.route("/batch_status", methods=["POST"])
@authenticated
def batch_status(user: User):
    """Check the status of a task.

    Parameters
    ----------
    user : User
        The primary identity of the user
    task_id : str
        The task uuid to look up

    Returns
    -------
    json
        The status of the task
    """
    app.logger.debug(f"request : {request.json}")
    results = get_tasks_from_redis(request.json["task_ids"], user)

    return jsonify({"response": "batch", "results": results})


@funcx_api.route("/containers/<container_id>/<container_type>", methods=["GET"])
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


@funcx_api.route("/containers", methods=["POST"])
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


def register_with_hub(address, endpoint_id, endpoint_address):
    """This registers with the Forwarder micro service.

    Can be used as an example of how to make calls this it, while the main API
    is updated to do this calling on behalf of the endpoint in the second iteration.

    Parameters
    ----------
    address : str
       Address of the forwarder service of the form http://<IP_Address>:<Port>

    """
    print(address + "/register")
    try:
        r = requests.post(
            address + "/register",
            json={
                "endpoint_id": endpoint_id,
                "redis_address": app.config["ADVERTISED_REDIS_HOST"],
                "endpoint_addr": endpoint_address,
            },
            timeout=2,  # timeout for the forwarder response
        )
    except requests.Timeout:
        raise ForwarderRegistrationError(
            "Forwarder is un-responsive, unable to register endpoint within timeout:2s"
        )
    except Exception as e:
        raise ForwarderRegistrationError(
            f"Request to Forwarder failed, unable to register endpoint: {e}"
        )

    if r.status_code != 200:
        print(dir(r))
        print(r)
        raise ForwarderRegistrationError(r.reason)

    return r.json()


def get_forwarder_version():
    forwarder_ip = app.config["FORWARDER_IP"]
    r = requests.get(f"http://{forwarder_ip}:8080/version", timeout=2)
    return r.json()


@funcx_api.route("/version", methods=["GET"])
def get_version():
    s = request.args.get("service")
    if s == "api" or s is None:
        return jsonify(VERSION)

    forwarder_v_info = get_forwarder_version()
    forwarder_version = forwarder_v_info["forwarder"]
    min_ep_version = forwarder_v_info["min_ep_version"]
    if s == "forwarder":
        return jsonify(forwarder_version)

    if s == "all":
        result = {
            "api": VERSION,
            "forwarder": forwarder_version,
            "min_sdk_version": MIN_SDK_VERSION,
            "min_ep_version": min_ep_version,
        }

        if app.extensions["ContainerService"]:
            result["container_service"] = app.extensions[
                "ContainerService"
            ].get_version()["version"]
        return jsonify(result)

    raise RequestMalformed("unknown service type or other error.")


# Endpoint routes
@funcx_api.route("/endpoints", methods=["POST"])
@authenticated_w_uuid
def reg_endpoint(user: User, user_uuid: str):
    """
    Register an endpoint. Add this endpoint to the database and associate it with
    this user.

    Returns
    -------
    json
        A dict containing the endpoint details
    """
    app.logger.debug("register_endpoint triggered")
    app.logger.info(request.json)

    v_info = get_forwarder_version()
    min_ep_version = v_info["min_ep_version"]
    if "version" not in request.json:
        raise RequestKeyError(
            "Endpoint funcx version must be passed in the 'version' field."
        )

    if request.json["version"] < min_ep_version:
        raise EndpointOutdated(min_ep_version)

    # Cooley ALCF is the default used here.
    endpoint_ip_addr = "140.221.68.108"
    if request.environ.get("HTTP_X_FORWARDED_FOR") is None:
        endpoint_ip_addr = request.environ["REMOTE_ADDR"]
    else:
        endpoint_ip_addr = request.environ["HTTP_X_FORWARDED_FOR"]
    app.logger.info(f"Registering endpoint IP address as: {endpoint_ip_addr}")

    # always return the jsonified error response as soon as it is available below
    # to prevent further registration steps being taken after an error
    try:
        app.logger.debug(request.json["endpoint_name"])
        app.logger.info(f"requesting registration for {request.json}")
        endpoint_uuid = register_endpoint(
            user,
            request.json["endpoint_name"],
            "",  # use description from meta? why store here at all
            endpoint_uuid=request.json["endpoint_uuid"],
        )
        app.logger.info(f"Successfully registered {endpoint_uuid} in database")

    except KeyError as e:
        app.logger.exception("Missing keys in json request")
        raise RequestKeyError(str(e))

    except UserNotFound as e:
        app.logger.exception("User not found")
        raise e

    except ValueError:
        app.logger.exception("Invalid UUID sent for endpoint")
        raise InvalidUUID("Invalid endpoint UUID provided")

    except Exception as e:
        app.logger.exception("Caught error while registering endpoint")
        raise e

    try:
        forwarder_ip = app.config["FORWARDER_IP"]
        response = register_with_hub(
            f"http://{forwarder_ip}:8080", endpoint_uuid, endpoint_ip_addr
        )
        app.logger.info(f"Successfully registered {endpoint_uuid} with forwarder")

    except Exception as e:
        app.logger.exception("Caught error during forwarder initialization")
        raise e

    if "meta" in request.json and endpoint_uuid:
        ingest_endpoint(user.username, user_uuid, endpoint_uuid, request.json["meta"])
        app.logger.info(f"Ingested endpoint {endpoint_uuid}")

    try:
        return jsonify(response)
    except NameError:
        return "oof"


@funcx_api.route("/endpoints/<endpoint_id>/status", methods=["GET"])
@authenticated
def get_ep_stats(user: User, endpoint_id):
    """Retrieve the status updates from an endpoint.

    Parameters
    ----------
    user : User
        The primary identity of the user
    endpoint_id : str
        The endpoint uuid to look up

    Returns
    -------
    json
        The status of the endpoint
    """
    alive_threshold = (
        2 * 60
    )  # time in seconds since last heartbeat to be counted as alive
    last = 10

    user_id = user.id

    # Extract the token for endpoint verification
    token_str = request.headers.get("Authorization")
    token = str.replace(str(token_str), "Bearer ", "")

    if not authorize_endpoint(user_id, endpoint_id, None, token):
        raise EndpointAccessForbidden(endpoint_id)

    rc = g_redis_client()

    status = {"status": "offline", "logs": []}
    try:
        end = min(rc.llen(f"ep_status_{endpoint_id}"), last)
        print("Total len :", end)
        items = rc.lrange(f"ep_status_{endpoint_id}", 0, end)
        if items:
            for i in items:
                status["logs"].append(json.loads(i))

            # timestamp is an epoch timestamp
            logs = status["logs"]  # should have been json loaded already
            newest_timestamp = logs[0]["timestamp"]
            now = time.time()
            if now - newest_timestamp < alive_threshold:
                status["status"] = "online"

    except Exception as e:
        raise EndpointStatsError(endpoint_id, str(e))

    return jsonify(status)


@funcx_api.route("/endpoints/<endpoint_id>", methods=["DELETE"])
@authenticated
def del_endpoint(user: User, endpoint_id):
    """Delete the endpoint.

    Parameters
    ----------
    user : User
        The primary identity of the user
    endpoint_id : str
        The endpoint uuid to delete

    Returns
    -------
    json
        Dict containing the result
    """
    try:
        result = Endpoint.delete_endpoint(user, endpoint_id)
        return jsonify({"result": result})
    except Exception as e:
        app.logger.error(e)


# Whitelist routes
@funcx_api.route("/endpoints/<endpoint_id>/whitelist", methods=["POST", "GET"])
@authenticated
def endpoint_whitelist(user: User, endpoint_id):
    """Get or insert into the endpoint's whitelist.
    If POST, insert the list of function ids into the whitelist.
    if GET, return the list of function ids in the whitelist

    Parameters
    ----------
    user : User
        The primary identity of the user
    endpoint_id : str
        The id of the endpoint

    Returns
    -------
    json
        A dict including a list of whitelisted functions for this endpoint
    """

    app.logger.info(
        f"Adding to endpoint {endpoint_id} whitelist by user: {user.username}"
    )

    if request.method == "GET":
        return get_ep_whitelist(user, endpoint_id)
    else:
        # Otherwise we need the list of functions passed in
        try:
            post_req = request.json
            functions = post_req["func"]
        except KeyError as e:
            raise RequestKeyError(str(e))
        except Exception as e:
            raise RequestMalformed(str(e))
        return add_ep_whitelist(user, endpoint_id, functions)


@funcx_api.route("/endpoints/<endpoint_id>/whitelist/<function_id>", methods=["DELETE"])
@authenticated
def del_endpoint_whitelist(user: User, endpoint_id, function_id):
    """Delete from an endpoint's whitelist. Return the success/failure of the delete.

    Parameters
    ----------
    user : User
        The primary identity of the user
    endpoint_id : str
        The id of the endpoint
    function_id : str
        The id of the function to delete

    Returns
    -------
    json
        A dict describing the result of deleting from the endpoint's whitelist
    """

    app.logger.info(
        f"Deleting function {function_id} from endpoint {endpoint_id} whitelist by "
        f"user: {user.username}"
    )

    return delete_ep_whitelist(user, endpoint_id, function_id)


@funcx_api.route("/functions", methods=["POST"])
@authenticated_w_uuid
def reg_function(user: User, user_uuid):
    """Register the function.

    Parameters
    ----------
    user : str
        The primary identity of the user

    POST Payload
    ------------
    { "function_name" : <FN_NAME>,
      "entry_point" : <ENTRY_POINT>,
      "function_code" : <ENCODED_FUNCTION_BODY>,
      "function_source": <UNENCODED FUNCTION BODY"?
      "container_uuid" : <CONTAINER_UUID>,
      "description" : <DESCRIPTION>,
      "group": <GLOBUS GROUP ID>
      "public" : <BOOL>
      "searchable" : <BOOL>
    }

    Returns
    -------
    json
        Dict containing the function details
    """

    function_rec = None
    function_source = None
    try:
        function_source = request.json["function_source"]
        function_rec = Function(
            function_uuid=str(uuid.uuid4()),
            function_name=request.json["function_name"],
            entry_point=request.json["entry_point"],
            description=request.json["description"],
            function_source_code=request.json["function_code"],
            public=request.json.get("public", False),
            user_id=user.id,
        )

        container_uuid = request.json.get("container_uuid", None)
        container = None
        if container_uuid:
            container = Container.find_by_uuid(container_uuid)
            if not container:
                raise ContainerNotFound(container_uuid)

        group_uuid = request.json.get("group", None)
        searchable = request.json.get("searchable", True)

        app.logger.info(
            f"Registering function {function_rec.function_name} "
            f"with container {container_uuid}"
        )

        if container:
            function_rec.container = FunctionContainer(
                function=function_rec, container=container
            )

        if group_uuid:
            function_rec.auth_groups = [
                FunctionAuthGroup(group_id=group_uuid, function=function_rec)
            ]

        function_rec.save_to_db()

        response = jsonify({"function_uuid": function_rec.function_uuid})

        if not searchable:
            return response

    except KeyError as key_error:
        app.logger.error(key_error)
        raise RequestKeyError(str(key_error))

    except Exception as e:
        message = (
            f"Function registration failed for user:{user.username} "
            f"function_name:{function_rec.function_name} due to {e}"
        )
        app.logger.error(message)
        raise InternalError(message)

    try:
        ingest_function(function_rec, function_source, user_uuid)
    except Exception as e:
        message = (
            f"Function ingest to search failed for user:{user.username} "
            f"function_name:{function_rec.function_name} due to {e}"
        )
        app.logger.error(message)
        raise InternalError(message)

    return response


@funcx_api.route("/functions/<function_id>", methods=["PUT"])
@authenticated
def upd_function(user: User, function_id):
    """Update the function.

    Parameters
    ----------
    user : User
        The primary identity of the user
    function_id : str
        The function to update

    Returns
    -------
    json
        Dict containing the result as an integer
    """
    try:
        function_name = request.json["name"]
        function_desc = request.json["desc"]
        function_entry_point = request.json["entry_point"]
        function_code = request.json["code"]
        result = update_function(
            user.username,
            function_id,
            function_name,
            function_desc,
            function_entry_point,
            function_code,
        )
        if result == 302:
            return jsonify({"function_uuid": function_id}), 302
        elif result == 403:
            message = (
                f"Unable to update function for user:{user.username} "
                f"function_id:{function_id}. 403 Unauthorized"
            )
            app.logger.error(message)
            raise InternalError(message)
        elif result == 404:
            message = (
                f"Unable to update function for user:{user.username} "
                f"function_id:{function_id}. 404 Function not found."
            )
            app.logger.error(message)
            raise InternalError(message)
    except Exception as e:
        app.logger.exception(e)
        message = (
            "Unable to update function for user:{} function_id:{} due to {}".format(
                user.username, function_id, e
            )
        )
        app.logger.error(message)
        raise InternalError(message)


@funcx_api.route("/functions/<function_id>", methods=["DELETE"])
@authenticated
def del_function(user: User, function_id):
    """Delete the function.

    Parameters
    ----------
    user : User
        The primary identity of the user
    function_id : str
        The function uuid to delete

    Returns
    -------
    json
        Dict containing the result
    """
    try:
        result = delete_function(user, function_id)
        return jsonify({"result": result})
    except Exception as e:
        app.logger.error(e)


@funcx_api.route("/stats", methods=["GET"])
def funcx_stats():
    """Get various usage stats."""
    app.logger.debug("Getting stats")
    try:
        rc = g_redis_client()
        result = int(rc.get("funcx_invocation_counter"))
        return jsonify({"total_function_invocations": result}), 200
    except Exception as e:
        app.logger.exception(e)
        message = f"Unable to get invocation count due to {e}"
        app.logger.error(message)
        raise InternalError(message)


@funcx_api.route("/authenticate", methods=["GET"])
@authenticated
def authenticate(user: User):
    return "OK"


@funcx_api.route("/task_groups/<task_group_id>", methods=["GET"])
@authenticated
def get_batch_info(user: User, task_group_id):
    rc = g_redis_client()

    if not TaskGroup.exists(rc, task_group_id):
        raise TaskGroupNotFound(task_group_id)

    task_group = TaskGroup(rc, task_group_id)

    if task_group.user_id != user.id:
        raise TaskGroupAccessForbidden(task_group_id)

    return jsonify({"authorized": True})
