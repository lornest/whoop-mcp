"""
WHOOP API Client

Handles authentication and API requests to the WHOOP API v2.
Uses authlib for OAuth 2.0/2.1 compliance per MCP security guidance.
"""

import logging
import time

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from secure_token_storage import TokenData, get_storage_backend

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.prod.whoop.com"
TOKEN_URL = f"{API_BASE_URL}/oauth/oauth2/token"


class WhoopOAuth2Client:
    def __init__(self, token_data: TokenData):
        self.storage = get_storage_backend()

        self.oauth_client = AsyncOAuth2Client(
            client_id=token_data.client_id,
            client_secret=token_data.client_secret,
            token_endpoint=TOKEN_URL,
            token_endpoint_auth_method="client_secret_post",  # Whoop requires this
            token=self._create_token_dict(token_data),
            update_token=self._save_token_callback,
        )

    def _create_token_dict(self, token_data: TokenData) -> dict:
        """Convert TokenData to authlib token format."""
        return {
            "access_token": token_data.access_token,
            "refresh_token": token_data.refresh_token,
            "token_type": "Bearer",
            "expires_at": token_data.expires_at or (time.time() + 3600),
        }

    async def _save_token_callback(self, token: dict, refresh_token: str = None):
        """
        Called by authlib when token is refreshed.

        Automatically persists tokens to secure storage.
        """
        token_data = TokenData(
            access_token=token["access_token"],
            refresh_token=token.get("refresh_token") or refresh_token,
            client_id=self.oauth_client.client_id,
            client_secret=self.oauth_client.client_secret,
            expires_at=token.get("expires_at"),
            created_at=time.time(),
        )
        self.storage.save_tokens(token_data)
        logger.info("Tokens refreshed and saved to secure storage")


class WhoopAPIClient:
    """Client for interacting with the WHOOP API v2."""

    def __init__(self, oauth_client: WhoopOAuth2Client):
        """Initialize API client with OAuth client."""
        self.oauth_client = oauth_client
        self.base_url = API_BASE_URL

    async def _make_request(self, method: str, url: str, **kwargs) -> dict:
        """
        Make authenticated API request.

        Automatically handles token expiry checking and refresh.
        """
        try:
            response = await self.oauth_client.oauth_client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("Rate limit exceeded")
                raise ValueError("WHOOP API rate limit exceeded. Please try again later.")
            elif e.response.status_code == 401:
                logger.error("Authentication failed")
                raise ValueError("Invalid or expired access token. Please re-authenticate.")
            else:
                logger.error(f"HTTP error occurred: {e}")
                raise

        except httpx.RequestError as e:
            logger.error(f"Network error occurred: {e}")
            raise ValueError(f"Failed to connect to WHOOP API: {str(e)}")

    async def get_user_profile(self) -> dict:
        """Get the authenticated user's body measurements (height, weight, max HR)."""
        return await self._make_request(
            "GET", f"{self.base_url}/developer/v2/user/measurement/body"
        )

    async def get_cycles(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 25,
    ) -> dict:
        """
        Get physiological cycles for a date range.

        Args:
            start_date: ISO 8601 formatted start date (e.g., "2024-01-01T00:00:00.000Z")
            end_date: ISO 8601 formatted end date
            limit: Maximum number of records to return (default 25)
        """
        params = {"limit": limit}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date

        return await self._make_request("GET", f"{self.base_url}/developer/v2/cycle", params=params)

    async def get_recovery(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 25,
    ) -> dict:
        """
        Get recovery data for a date range.

        Args:
            start_date: ISO 8601 formatted start date
            end_date: ISO 8601 formatted end date
            limit: Maximum number of records to return (default 25)
        """
        params = {"limit": limit}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date

        return await self._make_request(
            "GET", f"{self.base_url}/developer/v2/recovery", params=params
        )

    async def get_sleep(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 25,
    ) -> dict:
        """
        Get sleep data for a date range.

        Args:
            start_date: ISO 8601 formatted start date
            end_date: ISO 8601 formatted end date
            limit: Maximum number of records to return (default 25)
        """
        params = {"limit": limit}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date

        return await self._make_request(
            "GET", f"{self.base_url}/developer/v2/activity/sleep", params=params
        )

    async def get_workouts(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 25,
    ) -> dict:
        """
        Get workout data for a date range.

        Args:
            start_date: ISO 8601 formatted start date
            end_date: ISO 8601 formatted end date
            limit: Maximum number of records to return (default 25)
        """
        params = {"limit": limit}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date

        return await self._make_request(
            "GET", f"{self.base_url}/developer/v2/activity/workout", params=params
        )
