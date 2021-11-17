from unittest import mock

from funcx_web_service.models.tasks import RedisTask
from funcx_web_service.models.user import User


def test_get_status(
    flask_test_client, in_mock_auth_state, mock_redis_task_factory, mock_user: User
):
    mock_redis_task_factory("42")
    result = flask_test_client.get(
        "/api/v1/tasks/42", headers={"Authorization": "my_token"}
    )
    assert result.status_code == 200
    assert result.json["task_id"] == "42", result.json


def test_unauthorized_get_status(
    flask_test_client, in_mock_auth_state, mock_redis_task_factory, mock_user: User
):
    """
    Verify that a user cannot retrieve a Task status which is not theirs
    """
    mock_redis_task_factory("42", user_id=123)
    result = flask_test_client.get(
        "/api/v1/tasks/42", headers={"Authorization": "my_token"}
    )
    assert result.status_code == 404
    assert result.json["status"] == "Failed", result.json


def test_get_batch_status(
    flask_test_client,
    in_mock_auth_state,
    mock_redis,
    mock_redis_task_factory,
    mock_user: User,
):
    mock_redis_task_factory("1")
    mock_redis_task_factory("2")
    mock_redis.hset("task_2", "result", "foo-some-result")

    response = flask_test_client.post(
        "/api/v1/batch_status",
        headers={"Authorization": "my_token"},
        json={"task_ids": ["1", "2"]},
    )
    assert response
    data = response.json
    assert data["response"] == "batch"
    results = data["results"]
    assert len(results) == 2
    assert {"1", "2"} == set(results.keys())
    for task_data in results.values():
        assert "completion_t" in task_data, data
        assert "status" in task_data, data
    assert results["2"]["result"] == "foo-some-result"


def test_unauthorized_get_batch_status(
    flask_test_client, mocker, in_mock_auth_state, mock_redis_task_factory, mock_redis
):
    """
    Verify that a user cannot retrieve a status for a Batch which is not theirs
    """
    mock_redis_task_factory("1", user_id=123)
    mock_redis_task_factory("2", user_id=123)

    exists_spy = mocker.spy(RedisTask, "exists")

    result = flask_test_client.post(
        "/api/v1/batch_status",
        headers={"Authorization": "my_token"},
        json={"task_ids": ["1", "2"]},
    )

    assert result.status_code == 200
    assert "results" in result.json, result.json
    assert "1" in result.json["results"]
    assert "2" in result.json["results"]
    for task_id in result.json["results"]:
        assert result.json["results"][task_id]["reason"] == "Unknown task id"
        assert result.json["results"][task_id]["status"] == "Failed"

    exists_spy.assert_has_calls(
        [mock.call(mock_redis, "1"), mock.call(mock_redis, "2")]
    )
