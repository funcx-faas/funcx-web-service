from tests.routes.app_test_base import AppTestBase


class TestAuth(AppTestBase):

    def test_callback_no_code(self, mocker):
        mock_client = mocker.Mock()
        mock_client.oauth2_start_flow = mocker.Mock()
        mock_client.oauth2_get_authorize_url = mocker.Mock(return_value="http://secure.org")
        mocker.patch("funcx_web_service.routes.auth.get_auth_client", return_value=mock_client)

        client = self.test_client()
        result = client.get("/callback")
        assert result.status_code == 302
        assert result.headers['Location'] == 'http://secure.org'

    def test_callback_error(self, mocker):
        mock_flash = mocker.patch("funcx_web_service.routes.auth.flash")
        mocker.patch("funcx_web_service.routes.auth.url_for", return_value="http://funcx.home")

        client = self.test_client()

        result = client.get('/callback?error=FATAL&error_description="bad stuff"')
        assert result.status_code == 302
        assert result.headers['Location'] == 'http://funcx.home'
        assert mock_flash.call_args[0][0] == 'You could not be logged into funcX: "bad stuff"'

    def test_callback_with_code(self, mocker):
        mock_client = mocker.Mock()
        mock_client.oauth2_start_flow = mocker.Mock()
        mock_tokens = mocker.Mock()
        mock_tokens.decode_id_token = mocker.Mock(return_value={
            "preferred_username": "Bob",
            "name": "Bob D",
            "email": "bob@bob.com"
        })
        mock_tokens.by_resource_server = "xxxyyy"

        mock_client.oauth2_exchange_code_for_tokens = mocker.Mock(return_value=mock_tokens)
        mocker.patch("funcx_web_service.routes.auth.get_auth_client", return_value=mock_client)

        client = self.test_client()

        result = client.get("/callback?code=foo")
        assert result.status_code == 302
        assert result.headers['Location'] == 'https://dev.funcx.org/home'
        mock_client.oauth2_start_flow.assert_called_with("http://testhost/callback",
                                                         requested_scopes=[
                                                             'https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all',
                                                             'profile',
                                                             'urn:globus:auth:scope:transfer.api.globus.org:all',
                                                             'urn:globus:auth:scope:auth.globus.org:view_identities',
                                                             'openid'],
                                                         refresh_tokens=False
                                                         )
        mock_client.oauth2_exchange_code_for_tokens.assert_called_with("foo")
        mock_tokens.decode_id_token.assert_called_with(mock_client)
