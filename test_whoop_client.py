import time
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from secure_token_storage import TokenData
from whoop_client import (
    API_BASE_URL,
    TOKEN_URL,
    WhoopAPIClient,
    WhoopOAuth2Client,
)

# ==============================================================================
# WhoopOAuth2Client Tests
# ==============================================================================


class TestWhoopOAuth2Client:
    """Test suite for WhoopOAuth2Client."""

    @pytest.fixture
    def token_data(self):
        """Fixture providing sample TokenData."""
        return TokenData(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            expires_at=time.time() + 3600,
            created_at=time.time(),
        )

    @pytest.fixture
    def mock_storage(self):
        """Fixture providing mocked storage backend."""
        with patch("whoop_client.get_storage_backend") as mock_get_storage:
            mock_storage_instance = Mock()
            mock_get_storage.return_value = mock_storage_instance
            yield mock_storage_instance

    @pytest.fixture
    def mock_oauth_client(self, token_data):
        """Fixture providing mocked AsyncOAuth2Client."""
        with patch("whoop_client.AsyncOAuth2Client") as mock_oauth:
            mock_instance = AsyncMock()
            # Set client_id and client_secret on the mock instance
            mock_instance.client_id = token_data.client_id
            mock_instance.client_secret = token_data.client_secret
            mock_oauth.return_value = mock_instance
            yield mock_oauth

    def test_init_creates_oauth_client_with_correct_parameters(
        self,
        token_data,
        mock_storage,
        mock_oauth_client,  # type: ignore[arg-unused]
    ):
        """Test initialization creates OAuth client with correct parameters."""
        _ = mock_storage  # Fixture needed for side effect
        WhoopOAuth2Client(token_data)

        mock_oauth_client.assert_called_once()
        call_kwargs = mock_oauth_client.call_args[1]

        assert call_kwargs["client_id"] == token_data.client_id
        assert call_kwargs["client_secret"] == token_data.client_secret
        assert call_kwargs["token_endpoint"] == TOKEN_URL
        assert call_kwargs["token_endpoint_auth_method"] == "client_secret_post"
        assert "token" in call_kwargs
        assert "update_token" in call_kwargs

    def test_init_stores_storage_backend(self, token_data, mock_storage, mock_oauth_client):
        """Test initialization stores storage backend reference."""
        _ = mock_oauth_client  # Fixture needed for side effect
        client = WhoopOAuth2Client(token_data)

        assert client.storage is mock_storage

    def test_create_token_dict_with_all_fields(self, token_data, mock_storage, mock_oauth_client):
        """Test _create_token_dict creates proper token dictionary."""
        _ = mock_storage  # Fixture needed for side effect
        _ = mock_oauth_client  # Fixture needed for side effect
        client = WhoopOAuth2Client(token_data)

        token_dict = client._create_token_dict(token_data)

        assert token_dict["access_token"] == token_data.access_token
        assert token_dict["refresh_token"] == token_data.refresh_token
        assert token_dict["token_type"] == "Bearer"
        assert token_dict["expires_at"] == token_data.expires_at

    def test_create_token_dict_with_none_expires_at(self, mock_storage, mock_oauth_client):
        """Test _create_token_dict defaults expires_at when None."""
        _ = mock_storage  # Fixture needed for side effect
        _ = mock_oauth_client  # Fixture needed for side effect
        token_data = TokenData(
            access_token="token",
            refresh_token="refresh",
            client_id="client",
            client_secret="secret",
            expires_at=None,
            created_at=time.time(),
        )

        with patch("whoop_client.time.time", return_value=1000.0):
            client = WhoopOAuth2Client(token_data)
            token_dict = client._create_token_dict(token_data)

        assert token_dict["expires_at"] == 1000.0 + 3600

    def test_create_token_dict_preserves_existing_expires_at(
        self, token_data, mock_storage, mock_oauth_client
    ):
        """Test _create_token_dict preserves existing expires_at value."""
        _ = mock_storage  # Fixture needed for side effect
        _ = mock_oauth_client  # Fixture needed for side effect
        expected_expires = token_data.expires_at

        client = WhoopOAuth2Client(token_data)
        token_dict = client._create_token_dict(token_data)

        assert token_dict["expires_at"] == expected_expires

    @pytest.mark.asyncio
    async def test_save_token_callback_creates_token_data_correctly(
        self, token_data, mock_storage, mock_oauth_client
    ):
        """Test _save_token_callback creates TokenData with correct fields."""
        _ = mock_oauth_client  # Fixture needed for side effect
        client = WhoopOAuth2Client(token_data)

        new_token = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": time.time() + 7200,
        }

        with patch("whoop_client.time.time", return_value=2000.0):
            await client._save_token_callback(new_token)

        mock_storage.save_tokens.assert_called_once()
        saved_token_data = mock_storage.save_tokens.call_args[0][0]

        assert saved_token_data.access_token == new_token["access_token"]
        assert saved_token_data.refresh_token == new_token["refresh_token"]
        assert saved_token_data.client_id == token_data.client_id
        assert saved_token_data.client_secret == token_data.client_secret
        assert saved_token_data.expires_at == new_token["expires_at"]
        assert saved_token_data.created_at == 2000.0

    @pytest.mark.asyncio
    async def test_save_token_callback_uses_refresh_token_parameter_when_missing(
        self, token_data, mock_storage, mock_oauth_client
    ):
        """Test _save_token_callback uses refresh_token parameter when not in token dict."""
        _ = mock_oauth_client  # Fixture needed for side effect
        client = WhoopOAuth2Client(token_data)

        new_token = {
            "access_token": "new_access_token",
            "expires_at": time.time() + 7200,
        }
        refresh_token_param = "refresh_from_param"

        await client._save_token_callback(new_token, refresh_token=refresh_token_param)

        saved_token_data = mock_storage.save_tokens.call_args[0][0]
        assert saved_token_data.refresh_token == refresh_token_param

    @pytest.mark.asyncio
    async def test_save_token_callback_prefers_token_dict_refresh_token(
        self, token_data, mock_storage, mock_oauth_client
    ):
        """Test _save_token_callback prefers refresh_token from dict over parameter."""
        _ = mock_oauth_client  # Fixture needed for side effect
        client = WhoopOAuth2Client(token_data)

        new_token = {
            "access_token": "new_access_token",
            "refresh_token": "refresh_from_dict",
            "expires_at": time.time() + 7200,
        }
        refresh_token_param = "refresh_from_param"

        await client._save_token_callback(new_token, refresh_token=refresh_token_param)

        saved_token_data = mock_storage.save_tokens.call_args[0][0]
        assert saved_token_data.refresh_token == "refresh_from_dict"

    @pytest.mark.asyncio
    async def test_save_token_callback_saves_to_storage(
        self, token_data, mock_storage, mock_oauth_client
    ):
        """Test _save_token_callback persists tokens to storage."""
        _ = mock_oauth_client  # Fixture needed for side effect
        client = WhoopOAuth2Client(token_data)

        new_token = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": time.time() + 7200,
        }

        await client._save_token_callback(new_token)

        mock_storage.save_tokens.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_token_callback_handles_missing_expires_at(
        self, token_data, mock_storage, mock_oauth_client
    ):
        """Test _save_token_callback handles missing expires_at in token dict."""
        _ = mock_oauth_client  # Fixture needed for side effect
        client = WhoopOAuth2Client(token_data)

        new_token = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
        }

        await client._save_token_callback(new_token)

        saved_token_data = mock_storage.save_tokens.call_args[0][0]
        assert saved_token_data.expires_at is None


# ==============================================================================
# WhoopAPIClient Tests
# ==============================================================================


class TestWhoopAPIClient:
    """Test suite for WhoopAPIClient."""

    @pytest.fixture
    def token_data(self):
        """Fixture providing sample TokenData."""
        return TokenData(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            expires_at=time.time() + 3600,
            created_at=time.time(),
        )

    @pytest.fixture
    def mock_oauth_client(self, token_data):
        """Fixture providing mocked WhoopOAuth2Client."""
        with patch("whoop_client.get_storage_backend"):
            with patch("whoop_client.AsyncOAuth2Client"):
                oauth_client = WhoopOAuth2Client(token_data)
                oauth_client.oauth_client = AsyncMock()
                return oauth_client

    @pytest.fixture
    def api_client(self, mock_oauth_client):
        """Fixture providing WhoopAPIClient instance."""
        return WhoopAPIClient(mock_oauth_client)

    def test_init_stores_oauth_client(self, mock_oauth_client):
        """Test initialization stores OAuth client reference."""
        api_client = WhoopAPIClient(mock_oauth_client)

        assert api_client.oauth_client is mock_oauth_client

    def test_init_sets_base_url(self, mock_oauth_client):
        """Test initialization sets correct base URL."""
        api_client = WhoopAPIClient(mock_oauth_client)

        assert api_client.base_url == API_BASE_URL

    @pytest.mark.asyncio
    async def test_make_request_success_returns_json(self, api_client, mock_oauth_client):
        """Test _make_request returns JSON response on success."""
        expected_data = {"key": "value", "data": [1, 2, 3]}
        mock_response = Mock()
        mock_response.json.return_value = expected_data
        mock_response.raise_for_status = Mock()

        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        result = await api_client._make_request("GET", "https://api.test.com/endpoint")

        assert result == expected_data
        mock_response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_calls_oauth_client_with_correct_params(
        self, api_client, mock_oauth_client
    ):
        """Test _make_request calls OAuth client with correct parameters."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()

        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        url = "https://api.test.com/endpoint"
        params = {"param1": "value1"}
        headers = {"X-Custom": "header"}

        await api_client._make_request("POST", url, params=params, headers=headers)

        mock_oauth_client.oauth_client.request.assert_called_once_with(
            "POST", url, params=params, headers=headers
        )

    @pytest.mark.asyncio
    async def test_make_request_handles_401_unauthorized(self, api_client, mock_oauth_client):
        """Test _make_request raises ValueError on 401 unauthorized."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized", request=Mock(), response=mock_response
            )
        )

        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError, match="Invalid or expired access token"):
            await api_client._make_request("GET", "https://api.test.com/endpoint")

    @pytest.mark.asyncio
    async def test_make_request_handles_429_rate_limit(self, api_client, mock_oauth_client):
        """Test _make_request raises ValueError on 429 rate limit."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Rate limit exceeded", request=Mock(), response=mock_response
            )
        )

        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError, match="WHOOP API rate limit exceeded"):
            await api_client._make_request("GET", "https://api.test.com/endpoint")

    @pytest.mark.asyncio
    async def test_make_request_handles_other_http_errors(self, api_client, mock_oauth_client):
        """Test _make_request re-raises other HTTP status errors."""
        mock_response = Mock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=Mock(), response=mock_response)
        mock_response.raise_for_status = Mock(side_effect=error)

        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await api_client._make_request("GET", "https://api.test.com/endpoint")

    @pytest.mark.asyncio
    async def test_make_request_handles_network_errors(self, api_client, mock_oauth_client):
        """Test _make_request raises ValueError on network errors."""
        network_error = httpx.RequestError("Connection failed")
        mock_oauth_client.oauth_client.request = AsyncMock(side_effect=network_error)

        with pytest.raises(ValueError, match="Failed to connect to WHOOP API"):
            await api_client._make_request("GET", "https://api.test.com/endpoint")

    @pytest.mark.asyncio
    async def test_make_request_includes_error_message_in_network_error(
        self, api_client, mock_oauth_client
    ):
        """Test _make_request includes original error message in network errors."""
        network_error = httpx.RequestError("Specific connection error")
        mock_oauth_client.oauth_client.request = AsyncMock(side_effect=network_error)

        with pytest.raises(ValueError, match="Specific connection error"):
            await api_client._make_request("GET", "https://api.test.com/endpoint")

    @pytest.mark.asyncio
    async def test_get_user_profile_success(self, api_client):
        """Test get_user_profile returns user body measurements."""
        expected_data = {
            "user_id": 12345,
            "height_meter": 1.75,
            "weight_kilogram": 70.5,
            "max_heart_rate": 190,
        }

        with patch.object(api_client, "_make_request", new=AsyncMock(return_value=expected_data)):
            result = await api_client.get_user_profile()

        assert result == expected_data

    @pytest.mark.asyncio
    async def test_get_user_profile_calls_correct_endpoint(self, api_client):
        """Test get_user_profile calls correct API endpoint."""
        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_user_profile()

        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/user/measurement/body"
        )

    @pytest.mark.asyncio
    async def test_get_cycles_with_no_parameters(self, api_client):
        """Test get_cycles with default parameters."""
        expected_data = {"records": [{"id": 1}, {"id": 2}]}

        with patch.object(
            api_client, "_make_request", new=AsyncMock(return_value=expected_data)
        ) as mock_req:
            result = await api_client.get_cycles()

        assert result == expected_data
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/cycle", params={"limit": 25}
        )

    @pytest.mark.asyncio
    async def test_get_cycles_with_date_range(self, api_client):
        """Test get_cycles with start and end dates."""
        start_date = "2024-01-01T00:00:00.000Z"
        end_date = "2024-01-31T23:59:59.999Z"

        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_cycles(start_date=start_date, end_date=end_date)

        expected_params = {"limit": 25, "start": start_date, "end": end_date}
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/cycle", params=expected_params
        )

    @pytest.mark.asyncio
    async def test_get_cycles_with_custom_limit(self, api_client):
        """Test get_cycles with custom limit."""
        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_cycles(limit=50)

        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/cycle", params={"limit": 50}
        )

    @pytest.mark.asyncio
    async def test_get_cycles_with_only_start_date(self, api_client):
        """Test get_cycles with only start date."""
        start_date = "2024-01-01T00:00:00.000Z"

        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_cycles(start_date=start_date)

        expected_params = {"limit": 25, "start": start_date}
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/cycle", params=expected_params
        )

    @pytest.mark.asyncio
    async def test_get_cycles_with_only_end_date(self, api_client):
        """Test get_cycles with only end date."""
        end_date = "2024-01-31T23:59:59.999Z"

        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_cycles(end_date=end_date)

        expected_params = {"limit": 25, "end": end_date}
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/cycle", params=expected_params
        )

    @pytest.mark.asyncio
    async def test_get_recovery_with_no_parameters(self, api_client):
        """Test get_recovery with default parameters."""
        expected_data = {"records": [{"recovery_score": 85}]}

        with patch.object(
            api_client, "_make_request", new=AsyncMock(return_value=expected_data)
        ) as mock_req:
            result = await api_client.get_recovery()

        assert result == expected_data
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/recovery", params={"limit": 25}
        )

    @pytest.mark.asyncio
    async def test_get_recovery_with_date_range(self, api_client):
        """Test get_recovery with start and end dates."""
        start_date = "2024-01-01T00:00:00.000Z"
        end_date = "2024-01-31T23:59:59.999Z"

        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_recovery(start_date=start_date, end_date=end_date, limit=10)

        expected_params = {"limit": 10, "start": start_date, "end": end_date}
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/recovery", params=expected_params
        )

    @pytest.mark.asyncio
    async def test_get_sleep_with_no_parameters(self, api_client):
        """Test get_sleep with default parameters."""
        expected_data = {"records": [{"sleep_id": 1, "duration": 28800}]}

        with patch.object(
            api_client, "_make_request", new=AsyncMock(return_value=expected_data)
        ) as mock_req:
            result = await api_client.get_sleep()

        assert result == expected_data
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/activity/sleep", params={"limit": 25}
        )

    @pytest.mark.asyncio
    async def test_get_sleep_with_date_range(self, api_client):
        """Test get_sleep with start and end dates."""
        start_date = "2024-01-01T00:00:00.000Z"
        end_date = "2024-01-31T23:59:59.999Z"

        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_sleep(start_date=start_date, end_date=end_date, limit=15)

        expected_params = {"limit": 15, "start": start_date, "end": end_date}
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/activity/sleep", params=expected_params
        )

    @pytest.mark.asyncio
    async def test_get_workouts_with_no_parameters(self, api_client):
        """Test get_workouts with default parameters."""
        expected_data = {"records": [{"workout_id": 1, "sport_id": 1}]}

        with patch.object(
            api_client, "_make_request", new=AsyncMock(return_value=expected_data)
        ) as mock_req:
            result = await api_client.get_workouts()

        assert result == expected_data
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/activity/workout", params={"limit": 25}
        )

    @pytest.mark.asyncio
    async def test_get_workouts_with_date_range(self, api_client):
        """Test get_workouts with start and end dates."""
        start_date = "2024-01-01T00:00:00.000Z"
        end_date = "2024-01-31T23:59:59.999Z"

        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_workouts(start_date=start_date, end_date=end_date, limit=100)

        expected_params = {"limit": 100, "start": start_date, "end": end_date}
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/activity/workout", params=expected_params
        )


# ==============================================================================
# Error Handling Integration Tests
# ==============================================================================


class TestErrorHandlingIntegration:
    """Test error handling across both client classes."""

    @pytest.fixture
    def token_data(self):
        """Fixture providing sample TokenData."""
        return TokenData(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            expires_at=time.time() + 3600,
            created_at=time.time(),
        )

    @pytest.fixture
    def mock_oauth_client(self, token_data):
        """Fixture providing mocked WhoopOAuth2Client."""
        with patch("whoop_client.get_storage_backend"):
            with patch("whoop_client.AsyncOAuth2Client"):
                oauth_client = WhoopOAuth2Client(token_data)
                oauth_client.oauth_client = AsyncMock()
                return oauth_client

    @pytest.fixture
    def api_client(self, mock_oauth_client):
        """Fixture providing WhoopAPIClient instance."""
        return WhoopAPIClient(mock_oauth_client)

    @pytest.mark.asyncio
    async def test_401_error_on_get_user_profile(self, api_client, mock_oauth_client):
        """Test 401 error handling on get_user_profile."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized", request=Mock(), response=mock_response
            )
        )
        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError, match="Invalid or expired access token"):
            await api_client.get_user_profile()

    @pytest.mark.asyncio
    async def test_429_error_on_get_cycles(self, api_client, mock_oauth_client):
        """Test 429 rate limit handling on get_cycles."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError("Rate limit", request=Mock(), response=mock_response)
        )
        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError, match="rate limit exceeded"):
            await api_client.get_cycles()

    @pytest.mark.asyncio
    async def test_network_error_on_get_recovery(self, api_client, mock_oauth_client):
        """Test network error handling on get_recovery."""
        mock_oauth_client.oauth_client.request = AsyncMock(
            side_effect=httpx.RequestError("Network timeout")
        )

        with pytest.raises(ValueError, match="Failed to connect to WHOOP API"):
            await api_client.get_recovery()

    @pytest.mark.asyncio
    async def test_500_error_on_get_sleep(self, api_client, mock_oauth_client):
        """Test 500 server error handling on get_sleep."""
        mock_response = Mock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError("Server error", request=Mock(), response=mock_response)
        mock_response.raise_for_status = Mock(side_effect=error)
        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await api_client.get_sleep()

    @pytest.mark.asyncio
    async def test_403_error_on_get_workouts(self, api_client, mock_oauth_client):
        """Test 403 forbidden error handling on get_workouts."""
        mock_response = Mock()
        mock_response.status_code = 403
        error = httpx.HTTPStatusError("Forbidden", request=Mock(), response=mock_response)
        mock_response.raise_for_status = Mock(side_effect=error)
        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await api_client.get_workouts()


# ==============================================================================
# Edge Cases and Boundary Conditions
# ==============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def token_data(self):
        """Fixture providing sample TokenData."""
        return TokenData(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            expires_at=time.time() + 3600,
            created_at=time.time(),
        )

    @pytest.fixture
    def mock_oauth_client(self, token_data):
        """Fixture providing mocked WhoopOAuth2Client."""
        with patch("whoop_client.get_storage_backend"):
            with patch("whoop_client.AsyncOAuth2Client"):
                oauth_client = WhoopOAuth2Client(token_data)
                oauth_client.oauth_client = AsyncMock()
                return oauth_client

    @pytest.fixture
    def api_client(self, mock_oauth_client):
        """Fixture providing WhoopAPIClient instance."""
        return WhoopAPIClient(mock_oauth_client)

    @pytest.mark.asyncio
    async def test_get_cycles_with_limit_zero(self, api_client):
        """Test get_cycles with limit of zero."""
        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_cycles(limit=0)

        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/cycle", params={"limit": 0}
        )

    @pytest.mark.asyncio
    async def test_get_cycles_with_very_large_limit(self, api_client):
        """Test get_cycles with very large limit."""
        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_cycles(limit=10000)

        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/cycle", params={"limit": 10000}
        )

    @pytest.mark.asyncio
    async def test_get_cycles_with_empty_string_dates(self, api_client):
        """Test get_cycles handles empty string dates."""
        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_cycles(start_date="", end_date="")

        # Empty strings are falsy, so they should not be included
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/cycle", params={"limit": 25}
        )

    @pytest.mark.asyncio
    async def test_make_request_with_empty_json_response(self, api_client, mock_oauth_client):
        """Test _make_request handles empty JSON response."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = Mock()
        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        result = await api_client._make_request("GET", "https://api.test.com/endpoint")

        assert result == {}

    @pytest.mark.asyncio
    async def test_make_request_with_null_json_response(self, api_client, mock_oauth_client):
        """Test _make_request handles null JSON response."""
        mock_response = Mock()
        mock_response.json.return_value = None
        mock_response.raise_for_status = Mock()
        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        result = await api_client._make_request("GET", "https://api.test.com/endpoint")

        assert result is None

    @pytest.mark.asyncio
    async def test_make_request_with_array_json_response(self, api_client, mock_oauth_client):
        """Test _make_request handles array JSON response."""
        expected_data = [{"id": 1}, {"id": 2}, {"id": 3}]
        mock_response = Mock()
        mock_response.json.return_value = expected_data
        mock_response.raise_for_status = Mock()
        mock_oauth_client.oauth_client.request = AsyncMock(return_value=mock_response)

        result = await api_client._make_request("GET", "https://api.test.com/endpoint")

        assert result == expected_data

    @pytest.mark.asyncio
    async def test_save_token_callback_with_empty_token_dict(self, token_data):
        """Test _save_token_callback handles empty token dictionary."""
        with patch("whoop_client.get_storage_backend") as mock_get_storage:
            mock_storage = Mock()
            mock_get_storage.return_value = mock_storage

            with patch("whoop_client.AsyncOAuth2Client") as mock_oauth:
                mock_oauth_instance = AsyncMock()
                mock_oauth_instance.client_id = token_data.client_id
                mock_oauth_instance.client_secret = token_data.client_secret
                mock_oauth.return_value = mock_oauth_instance

                client = WhoopOAuth2Client(token_data)

                # Provide minimal token with fallback refresh_token
                new_token = {"access_token": "new_token"}

                await client._save_token_callback(new_token, refresh_token="fallback_refresh")

        saved_token_data = mock_storage.save_tokens.call_args[0][0]
        assert saved_token_data.access_token == "new_token"
        assert saved_token_data.refresh_token == "fallback_refresh"
        assert saved_token_data.expires_at is None

    def test_create_token_dict_with_zero_expires_at_uses_default(self, token_data):
        """Test _create_token_dict uses default when expires_at is 0 (falsy)."""
        token_data.expires_at = 0

        with patch("whoop_client.get_storage_backend"):
            with patch("whoop_client.AsyncOAuth2Client"):
                with patch("whoop_client.time.time", return_value=1000.0):
                    client = WhoopOAuth2Client(token_data)
                    token_dict = client._create_token_dict(token_data)

        # 0 is falsy, so it should use the default (current time + 3600)
        assert token_dict["expires_at"] == 1000.0 + 3600

    def test_create_token_dict_with_negative_expires_at(self, token_data):
        """Test _create_token_dict handles negative expires_at."""
        token_data.expires_at = -1000.0

        with patch("whoop_client.get_storage_backend"):
            with patch("whoop_client.AsyncOAuth2Client"):
                client = WhoopOAuth2Client(token_data)
                token_dict = client._create_token_dict(token_data)

        assert token_dict["expires_at"] == -1000.0

    @pytest.mark.asyncio
    async def test_get_recovery_with_all_parameters(self, api_client):
        """Test get_recovery with all parameters specified."""
        start_date = "2024-01-01T00:00:00.000Z"
        end_date = "2024-01-31T23:59:59.999Z"
        limit = 50

        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_recovery(start_date=start_date, end_date=end_date, limit=limit)

        expected_params = {"limit": 50, "start": start_date, "end": end_date}
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/recovery", params=expected_params
        )

    @pytest.mark.asyncio
    async def test_get_sleep_with_all_parameters(self, api_client):
        """Test get_sleep with all parameters specified."""
        start_date = "2024-01-01T00:00:00.000Z"
        end_date = "2024-01-31T23:59:59.999Z"
        limit = 75

        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_sleep(start_date=start_date, end_date=end_date, limit=limit)

        expected_params = {"limit": 75, "start": start_date, "end": end_date}
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/activity/sleep", params=expected_params
        )

    @pytest.mark.asyncio
    async def test_get_workouts_with_all_parameters(self, api_client):
        """Test get_workouts with all parameters specified."""
        start_date = "2024-01-01T00:00:00.000Z"
        end_date = "2024-01-31T23:59:59.999Z"
        limit = 200

        with patch.object(api_client, "_make_request", new=AsyncMock(return_value={})) as mock_req:
            await api_client.get_workouts(start_date=start_date, end_date=end_date, limit=limit)

        expected_params = {"limit": 200, "start": start_date, "end": end_date}
        mock_req.assert_called_once_with(
            "GET", f"{API_BASE_URL}/developer/v2/activity/workout", params=expected_params
        )


# ==============================================================================
# Token Management Integration Tests
# ==============================================================================


class TestTokenManagementIntegration:
    """Test token management and refresh logic."""

    @pytest.fixture
    def token_data(self):
        """Fixture providing sample TokenData."""
        return TokenData(
            access_token="original_access_token",
            refresh_token="original_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            expires_at=time.time() + 3600,
            created_at=time.time(),
        )

    @pytest.mark.asyncio
    async def test_token_refresh_updates_storage(self, token_data):
        """Test that token refresh properly updates storage."""
        with patch("whoop_client.get_storage_backend") as mock_get_storage:
            mock_storage = Mock()
            mock_get_storage.return_value = mock_storage

            with patch("whoop_client.AsyncOAuth2Client") as mock_oauth:
                mock_oauth_instance = AsyncMock()
                mock_oauth_instance.client_id = token_data.client_id
                mock_oauth_instance.client_secret = token_data.client_secret
                mock_oauth.return_value = mock_oauth_instance

                oauth_client = WhoopOAuth2Client(token_data)

                # Simulate token refresh
                new_token = {
                    "access_token": "refreshed_access_token",
                    "refresh_token": "refreshed_refresh_token",
                    "expires_at": time.time() + 7200,
                }

                await oauth_client._save_token_callback(new_token)

        # Verify storage was called
        mock_storage.save_tokens.assert_called_once()
        saved_data = mock_storage.save_tokens.call_args[0][0]

        assert saved_data.access_token == "refreshed_access_token"
        assert saved_data.refresh_token == "refreshed_refresh_token"

    @pytest.mark.asyncio
    async def test_oauth_client_stores_client_credentials(self, token_data):
        """Test OAuth client stores client credentials for token refresh."""
        with patch("whoop_client.get_storage_backend"):
            with patch("whoop_client.AsyncOAuth2Client") as mock_oauth:
                mock_oauth_instance = AsyncMock()
                mock_oauth_instance.client_id = token_data.client_id
                mock_oauth_instance.client_secret = token_data.client_secret
                mock_oauth.return_value = mock_oauth_instance

                oauth_client = WhoopOAuth2Client(token_data)

        # Verify client credentials are accessible
        assert oauth_client.oauth_client.client_id == token_data.client_id
        assert oauth_client.oauth_client.client_secret == token_data.client_secret

    def test_oauth_client_configures_whoop_specific_auth_method(self, token_data):
        """Test OAuth client uses Whoop-required auth method."""
        with patch("whoop_client.get_storage_backend"):
            with patch("whoop_client.AsyncOAuth2Client") as mock_oauth:
                WhoopOAuth2Client(token_data)

        call_kwargs = mock_oauth.call_args[1]
        assert call_kwargs["token_endpoint_auth_method"] == "client_secret_post"

    def test_oauth_client_configures_correct_token_endpoint(self, token_data):
        """Test OAuth client uses correct token endpoint."""
        with patch("whoop_client.get_storage_backend"):
            with patch("whoop_client.AsyncOAuth2Client") as mock_oauth:
                WhoopOAuth2Client(token_data)

        call_kwargs = mock_oauth.call_args[1]
        assert call_kwargs["token_endpoint"] == TOKEN_URL
        assert TOKEN_URL == f"{API_BASE_URL}/oauth/oauth2/token"
