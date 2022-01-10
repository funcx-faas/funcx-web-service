from funcx_web_service.models.tasks import TaskGroup


def test_get_batch_info(
    flask_test_client, mocker, mock_user, in_mock_auth_state, mock_redis
):
    TaskGroup(mock_redis, "123", user_id=mock_user.id)
    exists_spy = mocker.spy(TaskGroup, "exists")

    result = flask_test_client.get(
        "/api/v1/task_groups/123", headers={"Authorization": "my_token"}
    )
    assert result.json["authorized"]
    exists_spy.assert_called_with(mock_redis, "123")
