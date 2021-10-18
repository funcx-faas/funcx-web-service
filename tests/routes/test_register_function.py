from unittest.mock import ANY

from funcx_web_service.models.container import Container
from funcx_web_service.models.function import Function, FunctionAuthGroup
from funcx_web_service.models.user import User
from tests.routes.app_test_base import AppTestBase


class TestRegisterFunction(AppTestBase):
    def test_register_function(self, mock_auth_client, mocker):
        mock_ingest = mocker.patch("funcx_web_service.routes.funcx.ingest_function")
        client = self.client
        result = client.post(
            "api/v1/functions",
            json={
                "function_source": "def fun(x): return x+1",
                "function_name": "test fun",
                "entry_point": "func()",
                "description": "this is a test",
                "function_code": "flksdjfldkjdlkfjslk",
                "public": True,
            },
            headers={"Authorization": "my_token"},
        )
        assert result.status_code == 200
        assert "function_uuid" in result.json

        saved_function = Function.find_by_uuid(result.json["function_uuid"])
        assert saved_function.function_uuid == result.json["function_uuid"]
        assert saved_function.function_name == "test fun"
        assert saved_function.entry_point == "func()"
        assert saved_function.description == "this is a test"
        assert saved_function.function_source_code == "flksdjfldkjdlkfjslk"
        assert saved_function.public

        assert mock_ingest.call_args[0][0].function_uuid == result.json["function_uuid"]
        assert mock_ingest.call_args[0][1] == "def fun(x): return x+1"
        assert mock_ingest.call_args[0][2] == "123-456"

    def test_register_function_no_search(self, mock_auth_client, mocker):
        mock_ingest = mocker.patch("funcx_web_service.routes.funcx.ingest_function")
        client = self.client
        mock_user = User(id=42, username="bob")

        mocker.patch.object(User, "find_by_username", return_value=mock_user)
        result = client.post(
            "api/v1/functions",
            json={
                "function_source": "def fun(x): return x+1",
                "function_name": "test fun",
                "entry_point": "func()",
                "description": "this is a test",
                "function_code": "flksdjfldkjdlkfjslk",
                "public": True,
                "searchable": False,
            },
            headers={"Authorization": "my_token"},
        )
        assert result.status_code == 200
        assert "function_uuid" in result.json
        assert mock_ingest.not_called

    def test_register_function_with_container(self, mock_auth_client, mocker):
        mock_ingest = mocker.patch("funcx_web_service.routes.funcx.ingest_function")
        client = self.client
        mock_user = User(id=42, username="bob")
        mocker.patch.object(User, "find_by_username", return_value=mock_user)

        mock_container = Container(id=44)

        mock_container_read = mocker.patch.object(
            Container, "find_by_uuid", return_value=mock_container
        )
        result = client.post(
            "api/v1/functions",
            json={
                "function_source": "def fun(x): return x+1",
                "function_name": "test fun",
                "entry_point": "func()",
                "description": "this is a test",
                "function_code": "flksdjfldkjdlkfjslk",
                "public": True,
                "searchable": False,
                "container_uuid": "11122-22111",
            },
            headers={"Authorization": "my_token"},
        )
        assert result.status_code == 200
        assert "function_uuid" in result.json
        assert mock_ingest.not_called
        mock_container_read.assert_called_with("11122-22111")

        saved_function = Function.find_by_uuid(result.json["function_uuid"])
        assert saved_function.container.container_id == 44

    def test_register_function_with_group_auth(self, mock_auth_client, mocker):
        mock_ingest = mocker.patch("funcx_web_service.routes.funcx.ingest_function")
        client = self.client
        mock_user = User(id=42, username="bob")
        mocker.patch.object(User, "find_by_username", return_value=mock_user)

        mock_auth_group = FunctionAuthGroup(id=45)

        mock_authgroup_read = mocker.patch(
            "funcx_web_service.routes.funcx.FunctionAuthGroup"
        )
        mock_authgroup_read.return_value = mock_auth_group

        result = client.post(
            "api/v1/functions",
            json={
                "function_source": "def fun(x): return x+1",
                "function_name": "test fun",
                "entry_point": "func()",
                "description": "this is a test",
                "function_code": "flksdjfldkjdlkfjslk",
                "public": True,
                "searchable": False,
                "group": "222-111",
            },
            headers={"Authorization": "my_token"},
        )
        assert result.status_code == 200
        assert "function_uuid" in result.json
        assert mock_ingest.not_called
        mock_authgroup_read.assert_called_with(function=ANY, group_id="222-111")

        saved_function = Function.find_by_uuid(result.json["function_uuid"])
        assert len(saved_function.auth_groups) == 1
        assert saved_function.auth_groups[0].id == 45

    def test_update_function(self, mock_auth_client, mocker):
        mock_update = mocker.patch(
            "funcx_web_service.routes.funcx.update_function", return_value=302
        )
        client = self.client
        result = client.put(
            "api/v1/functions/123-45",
            json={
                "function_source": "def fun(x): return x+1",
                "name": "test fun",
                "desc": "this is a test",
                "entry_point": "func()",
                "code": "flksdjfldkjdlkfjslk",
                "public": True,
            },
            headers={"Authorization": "my_token"},
        )
        assert result.status_code == 302
        mock_update.assert_called_with(
            "bob",
            "123-45",
            "test fun",
            "this is a test",
            "func()",
            "flksdjfldkjdlkfjslk",
        )

    def test_delete_function(self, mock_auth_client, mock_user, mocker):
        mock_delete = mocker.patch(
            "funcx_web_service.routes.funcx.delete_function", return_value=302
        )
        client = self.client
        result = client.delete(
            "api/v1/functions/123-45", headers={"Authorization": "my_token"}
        )
        assert result.status_code == 200
        assert mock_delete.called_with("bob", "123-45")
