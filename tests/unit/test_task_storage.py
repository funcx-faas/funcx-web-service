import uuid

import boto3

from funcx_web_service import task_storage
from funcx_web_service.models.tasks import RedisTask


def test_redis_storage_threshold_no_env_var(monkeypatch):
    monkeypatch.delenv("FUNCX_REDIS_STORAGE_THRESHOLD", raising=False)
    val = task_storage.redis_storage_threshold()
    assert val == task_storage.DEFAULT_REDIS_STORAGE_THRESHOLD


def test_redis_storage_threshold_invalid_env_var(monkeypatch):
    monkeypatch.setenv("FUNCX_REDIS_STORAGE_THRESHOLD", "foo")
    val = task_storage.redis_storage_threshold()
    assert val == task_storage.DEFAULT_REDIS_STORAGE_THRESHOLD


def test_redis_storage_threshold_nondefault(monkeypatch):
    monkeypatch.setenv("FUNCX_REDIS_STORAGE_THRESHOLD", "foo")
    val = task_storage.redis_storage_threshold()
    assert val == task_storage.DEFAULT_REDIS_STORAGE_THRESHOLD


def test_s3_bucket_name_no_env_var(monkeypatch):
    monkeypatch.delenv("FUNCX_S3_BUCKET_NAME", raising=False)
    val = task_storage.s3_bucket_name()
    assert val is None
    assert not task_storage.use_storage_interface()


def test_s3_bucket_name_with_value(monkeypatch):
    monkeypatch.setenv("FUNCX_S3_BUCKET_NAME", "foo-bucket")
    val = task_storage.s3_bucket_name()
    assert val == "foo-bucket"
    assert task_storage.use_storage_interface()


# note: this test needs to execute within a flask request context because the task
# storage object is attached to flask.g
def test_s3_storage_read(flask_request_ctx, mock_redis, mock_s3_bucket):
    task_id = str(uuid.uuid1())
    s3key = f"{task_id}.result"

    # write task to S3 ("raw"), relying on mock_s3_bucket to activate moto.mock_s3
    s3client = boto3.client("s3")
    s3client.put_object(Body="foo", Bucket=mock_s3_bucket, Key=s3key)

    # construct a RedisTask with result_reference pointed at S3
    task = RedisTask(mock_redis, task_id=task_id)
    task.result_reference = {
        "storage_id": "s3",
        "s3bucket": mock_s3_bucket,
        "key": s3key,
    }

    # get the task storage result, it should be read from the mock S3
    result = task_storage.get_task_result(task)
    assert result == "foo"
