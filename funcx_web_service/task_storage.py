"""
This module wraps use of `funcx_common.task_storage`

The main entry point into this module should be the 'get_task_result' function, which
takes a task and returns the result.

It handles the following:
- attachment to flask.g
- loading from env vars
- dispatch over the presence/absence of the FUNCX_S3_BUCKET_NAME variable (to the
  legacy, non-S3 mechanism)
"""
import logging
import os
import typing as t

import flask
from funcx_common.task_storage import RedisS3Storage

from funcx_web_service.models.tasks import RedisTask

log = logging.getLogger(__name__)
DEFAULT_REDIS_STORAGE_THRESHOLD = 20000


def s3_bucket_name() -> t.Optional[str]:
    return os.getenv("FUNCX_S3_BUCKET_NAME")


def redis_storage_threshold() -> t.Optional[str]:
    val = os.getenv("FUNCX_REDIS_STORAGE_THRESHOLD")
    if val is not None:
        try:
            return int(val)
        except ValueError:
            log.warning(
                "could not parse FUNCX_REDIS_STORAGE_THRESHOLD=%s as int, "
                "will failover to default",
                val,
            )
    return DEFAULT_REDIS_STORAGE_THRESHOLD


def use_storage_interface() -> bool:
    return s3_bucket_name() is not None


def new_task_storage() -> RedisS3Storage:
    bucket = s3_bucket_name()
    threshold = redis_storage_threshold()
    return RedisS3Storage(bucket, redis_threshold=threshold)


def get_storage() -> t.Optional[RedisS3Storage]:
    if not use_storage_interface():
        return None

    if not hasattr(flask.g, "task_storage"):
        flask.g.task_storage = new_task_storage()
    return flask.g.task_storage


def get_task_result(task: RedisTask) -> t.Optional[str]:
    storage = get_storage()
    if storage is None:
        return task.result
    else:
        return storage.get_result(task)
