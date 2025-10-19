"""
WHOOP API Client

Handles authentication and API requests to the WHOOP API v2.
"""

import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

API_BASE_URL = "https://api.prod.whoop.com"
TOKEN_URL = f"{API_BASE_URL}/oauth/oauth2/token"


class TokenManager:
    """Manages access and refresh tokens with automatic refresh."""

    def __init__(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret

    async def refresh_access_token(self) -> str:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            raise ValueError("No refresh token available. Please re-authenticate.")

        if not self.client_id or not self.client_secret:
            raise ValueError("Client ID and Secret must be set to refresh tokens.")

        logger.info("Refreshing access token...")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(TOKEN_URL, data=data)
                response.raise_for_status()
                token_data = response.json()

                self.access_token = token_data["access_token"]
                if "refresh_token" in token_data:
                    self.refresh_token = token_data["refresh_token"]

                logger.info("Access token refreshed successfully")
                return self.access_token

            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to refresh token: {e}")
                raise ValueError(
                    "Failed to refresh access token. Please re-authenticate using bootstrap.py"
                )
            except Exception as e:
                logger.error(f"Error refreshing token: {e}")
                raise


class WhoopAPIClient:
    """Client for interacting with the WHOOP API v2."""

    def __init__(self, token_manager: TokenManager):
        self.token_manager = token_manager
        self.base_url = API_BASE_URL

    def _get_headers(self) -> dict:
        """Get authorization headers for API requests."""
        return {
            "Authorization": f"Bearer {self.token_manager.access_token}",
            "Content-Type": "application/json"
        }

    async def _make_request(self, method: str, url: str, **kwargs) -> dict:
        """Make an HTTP request with automatic token refresh on 401."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=self._get_headers(), **kwargs)
                elif method == "POST":
                    response = await client.post(url, headers=self._get_headers(), **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                # Try to refresh token on 401 Unauthorized
                if e.response.status_code == 401 and self.token_manager.refresh_token:
                    logger.info("Access token expired, attempting refresh...")
                    await self.token_manager.refresh_access_token()

                    # Retry the request with new token
                    if method == "GET":
                        response = await client.get(url, headers=self._get_headers(), **kwargs)
                    elif method == "POST":
                        response = await client.post(url, headers=self._get_headers(), **kwargs)

                    response.raise_for_status()
                    return response.json()

                # Handle other HTTP errors
                elif e.response.status_code == 429:
                    logger.error("Rate limit exceeded.")
                    raise ValueError("WHOOP API rate limit exceeded. Please try again later.")
                elif e.response.status_code == 401:
                    logger.error("Authentication failed and no refresh token available.")
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
            "GET",
            f"{self.base_url}/developer/v2/user/measurement/body"
        )

    async def get_cycles(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 25
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

        return await self._make_request(
            "GET",
            f"{self.base_url}/developer/v2/cycle",
            params=params
        )

    async def get_recovery(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 25
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
            "GET",
            f"{self.base_url}/developer/v2/recovery",
            params=params
        )

    async def get_sleep(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 25
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
            "GET",
            f"{self.base_url}/developer/v2/activity/sleep",
            params=params
        )

    async def get_workouts(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 25
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
            "GET",
            f"{self.base_url}/developer/v2/activity/workout",
            params=params
        )
