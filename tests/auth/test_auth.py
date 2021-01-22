import pytest

from funcx_web_service.authentication.auth import authorize_endpoint, authorize_function
from funcx_web_service.models.function import Function, FunctionAuthGroup


class TestAuth:
    def test_authorize_endpoint_restricted_whitelist(self, mocker, test_app_context):
        """
        Test to see that we are authorized if the endpoint is restricted, but the
        requested function is in the whitelist
        """
        from funcx_web_service.models.endpoint import Endpoint
        authorize_endpoint.cache_clear()
        mock_endpoint_find = mocker.patch.object(Endpoint,
                                                 "find_by_uuid",
                                                 return_value=Endpoint(
                                                     public=True,
                                                     restricted=True,
                                                     restricted_functions=[
                                                         Function(function_uuid="123")
                                                     ]
                                                 ))
        result = authorize_endpoint(user_id="test_user",
                                    endpoint_uuid="123-45-566",
                                    function_uuid="123",
                                    token="ttttt")
        assert result
        mock_endpoint_find.assert_called_with("123-45-566")

    def test_authorize_endpoint_restricted_not_whitelist(self, mocker, test_app_context):
        """
        Test to see that we are authorized if the endpoint is restricted, and the
        requested function is not in the whitelist
        """
        from funcx_web_service.models.endpoint import Endpoint
        authorize_endpoint.cache_clear()

        mock_endpoint_find = mocker.patch.object(Endpoint,
                                                 "find_by_uuid",
                                                 return_value=Endpoint(
                                                     public=True,
                                                     restricted=True,
                                                     restricted_functions=[
                                                         Function(function_uuid="456")
                                                     ]
                                                 ))

        with pytest.raises(Exception) as excinfo:
            authorize_endpoint(user_id="test_user",
                               endpoint_uuid="123-45-566",
                               function_uuid="123",
                               token="ttttt")
            print(excinfo)
            mock_endpoint_find.assert_called_with("123-45-566")

    def test_authorize_endpoint_public(self, mocker, test_app_context):
        from funcx_web_service.models.endpoint import Endpoint
        authorize_endpoint.cache_clear()

        mock_endpoint_find = mocker.patch.object(Endpoint,
                                                 "find_by_uuid",
                                                 return_value=Endpoint(
                                                     public=True,
                                                     restricted=False
                                                 ))
        result = authorize_endpoint(user_id="test_user",
                                    endpoint_uuid="123-45-566",
                                    function_uuid="123",
                                    token="ttttt")
        assert result
        mock_endpoint_find.assert_called_with("123-45-566")

    def test_authorize_endpoint_user(self, mocker, test_app_context):
        from funcx_web_service.models.endpoint import Endpoint
        authorize_endpoint.cache_clear()

        mock_endpoint_find = mocker.patch.object(Endpoint,
                                                 "find_by_uuid",
                                                 return_value=Endpoint(
                                                     public=False,
                                                     restricted=False,
                                                     user_id=42
                                                 ))
        result = authorize_endpoint(user_id=42,
                                    endpoint_uuid="123-45-566",
                                    function_uuid="123",
                                    token="ttttt")
        assert result
        mock_endpoint_find.assert_called_with("123-45-566")

    def test_authorize_endpoint_group(self, mocker, test_app_context):
        from funcx_web_service.models.endpoint import Endpoint
        from funcx_web_service.models.auth_groups import AuthGroup
        authorize_endpoint.cache_clear()

        mock_endpoint_find = mocker.patch.object(Endpoint,
                                                 "find_by_uuid",
                                                 return_value=Endpoint(
                                                     public=False,
                                                     restricted=False,
                                                     user_id=1
                                                 ))
        mock_auth_group_find = mocker.patch.object(AuthGroup,
                                                   "find_by_endpoint_uuid",
                                                   return_value=[
                                                       AuthGroup(group_id="my-group",
                                                                 endpoint_id="123-45-566")
                                                   ])
        import funcx_web_service.authentication
        mock_check_group_membership = mocker.patch.object(
            funcx_web_service.authentication.auth,
            "check_group_membership",
            return_value=True)

        result = authorize_endpoint(user_id=42,
                                    endpoint_uuid="123-45-566",
                                    function_uuid="123",
                                    token="ttttt")
        assert result
        mock_endpoint_find.assert_called_with("123-45-566")
        mock_auth_group_find.assert_called_with("123-45-566")
        mock_check_group_membership.assert_called_with("ttttt", ['my-group'])

    def test_authorize_endpoint_no_group(self, mocker, test_app_context):
        from funcx_web_service.models.endpoint import Endpoint
        from funcx_web_service.models.auth_groups import AuthGroup
        authorize_endpoint.cache_clear()

        mock_endpoint_find = mocker.patch.object(Endpoint,
                                                 "find_by_uuid",
                                                 return_value=Endpoint(
                                                     public=False,
                                                     restricted=False,
                                                     user_id=1
                                                 ))
        mock_auth_group_find = mocker.patch.object(AuthGroup,
                                                   "find_by_endpoint_uuid",
                                                   return_value=[])
        import funcx_web_service.authentication
        mock_check_group_membership = mocker.patch.object(
            funcx_web_service.authentication.auth,
            "check_group_membership",
            return_value=True)

        result = authorize_endpoint(user_id=42,
                                    endpoint_uuid="123-45-566",
                                    function_uuid="123",
                                    token="ttttt")
        assert not result
        mock_endpoint_find.assert_called_with("123-45-566")
        mock_auth_group_find.assert_called_with("123-45-566")
        mock_check_group_membership.assert_not_called()

    def test_authorize_function_user_owns(self, mocker, test_app_context):
        from funcx_web_service.models.function import Function
        authorize_function.cache_clear()

        mock_function_find = mocker.patch.object(Function,
                                                 "find_by_uuid",
                                                 return_value=Function(
                                                     public=False,
                                                     user_id=44
                                                 ))
        result = authorize_function(user_id=44,
                                    function_uuid="123",
                                    token="ttttt")
        assert result
        mock_function_find.assert_called_with("123")

    def test_authorize_function_public(self, mocker, test_app_context):
        from funcx_web_service.models.function import Function
        authorize_function.cache_clear()

        mock_function_find = mocker.patch.object(Function,
                                                 "find_by_uuid",
                                                 return_value=Function(
                                                     public=True,
                                                     user_id=1
                                                 ))
        result = authorize_function(user_id=44,
                                    function_uuid="123",
                                    token="ttttt")
        assert result
        mock_function_find.assert_called_with("123")

    def test_authorize_function_auth_group(self, mocker, test_app_context):
        from funcx_web_service.models.function import Function
        authorize_function.cache_clear()

        mock_function_find = mocker.patch.object(Function,
                                                 "find_by_uuid",
                                                 return_value=Function(
                                                     public=False,
                                                     user_id=1
                                                 ))

        import funcx_web_service.authentication
        mock_check_group_membership = mocker.patch.object(
            funcx_web_service.authentication.auth,
            "check_group_membership",
            return_value=True)

        mocker.patch.object(FunctionAuthGroup,
                            "find_by_function_uuid",
                            return_value=[
                                FunctionAuthGroup(
                                    group_id="my-group",
                                    function_id="123-45-566")
                            ])

        result = authorize_function(user_id=44,
                                    function_uuid="123",
                                    token="ttttt")
        assert result
        mock_function_find.assert_called_with("123")
        mock_check_group_membership.assert_called_with("ttttt", ['my-group'])
