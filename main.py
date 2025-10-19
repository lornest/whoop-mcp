"""
WHOOP MCP Server

An MCP server that provides access to WHOOP API v2 data including:
- User profile information
- Physiological cycles with recovery data
- Sleep data and metrics
- Workout data and activities

Requires OAuth 2.0 authentication.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, Any
import httpx
from fastmcp import FastMCP
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("whoop-mcp")

# Whoop API configuration
API_BASE_URL = "https://api.prod.whoop.com"
AUTH_URL = f"{API_BASE_URL}/oauth/oauth2/auth"
TOKEN_URL = f"{API_BASE_URL}/oauth/oauth2/token"

# OAuth credentials (to be set via environment variables)
CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("WHOOP_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("WHOOP_REFRESH_TOKEN")


class TokenManager:
    """Manages access and refresh tokens with automatic refresh."""

    def __init__(self, access_token: str, refresh_token: Optional[str] = None):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET

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

                # Update tokens
                self.access_token = token_data["access_token"]
                if "refresh_token" in token_data:
                    self.refresh_token = token_data["refresh_token"]

                logger.info("Access token refreshed successfully")
                return self.access_token

            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to refresh token: {e}")
                raise ValueError(
                    "Failed to refresh access token. Please re-authenticate using oauth_helper.py"
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
        """Get the authenticated user's profile information."""
        return await self._make_request(
            "GET",
            f"{self.base_url}/developer/v2/user/profile/basic"
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


def get_client() -> WhoopAPIClient:
    """Get an authenticated WHOOP API client."""
    if not ACCESS_TOKEN:
        raise ValueError(
            "WHOOP_ACCESS_TOKEN environment variable is not set. "
            "Please set it to your WHOOP API access token."
        )

    # Create token manager with refresh token support
    token_manager = TokenManager(ACCESS_TOKEN, REFRESH_TOKEN)
    return WhoopAPIClient(token_manager)


def format_workout(workout: dict) -> str:
    """Format a workout record into human-readable text."""
    lines = []

    # Header with sport name (prioritize over ID)
    sport = workout.get("sport_name", f"Sport ID {workout.get('sport_id', 'Unknown')}")
    start = workout.get("start", "")
    lines.append(f"Workout: {sport}")
    if start:
        lines.append(f"  Time: {start}")

    # Score data if available
    if workout.get("score_state") == "SCORED" and "score" in workout:
        score = workout["score"]
        if "strain" in score and score["strain"] is not None:
            lines.append(f"  Strain: {score['strain']}")
        if "average_heart_rate" in score and score["average_heart_rate"] is not None:
            lines.append(f"  Avg Heart Rate: {score['average_heart_rate']} bpm")
        if "max_heart_rate" in score and score["max_heart_rate"] is not None:
            lines.append(f"  Max Heart Rate: {score['max_heart_rate']} bpm")
        if "kilojoule" in score and score["kilojoule"] is not None:
            lines.append(f"  Energy: {score['kilojoule']} kJ")
        if "distance_meter" in score and score["distance_meter"] is not None:
            distance_km = score['distance_meter'] / 1000
            lines.append(f"  Distance: {distance_km:.2f} km")
        if "altitude_gain_meter" in score and score["altitude_gain_meter"] is not None:
            lines.append(f"  Altitude Gain: {score['altitude_gain_meter']} m")
        if "altitude_change_meter" in score and score["altitude_change_meter"] is not None:
            lines.append(f"  Altitude Change: {score['altitude_change_meter']} m")

    return "\n".join(lines)


def format_sleep(sleep: dict) -> str:
    """Format a sleep record into human-readable text."""
    lines = []

    # Header
    start = sleep.get("start", "")
    end = sleep.get("end", "")
    is_nap = sleep.get("nap", False)
    sleep_type = "Nap" if is_nap else "Sleep"
    lines.append(f"{sleep_type}: {start} to {end}")

    # Score data if available
    if sleep.get("score_state") == "SCORED" and "score" in sleep:
        score = sleep["score"]

        # Performance metrics
        if "sleep_performance_percentage" in score and score["sleep_performance_percentage"] is not None:
            lines.append(f"  Performance: {score['sleep_performance_percentage']}%")
        if "sleep_efficiency_percentage" in score and score["sleep_efficiency_percentage"] is not None:
            lines.append(f"  Efficiency: {score['sleep_efficiency_percentage']}%")
        if "respiratory_rate" in score and score["respiratory_rate"] is not None:
            lines.append(f"  Respiratory Rate: {score['respiratory_rate']} breaths/min")

        # Stage breakdown
        if "stage_summary" in score and score["stage_summary"] is not None:
            stages = score["stage_summary"]
            if "total_in_bed_time_milli" in stages and stages["total_in_bed_time_milli"] is not None:
                total_mins = stages["total_in_bed_time_milli"] / 1000 / 60
                lines.append(f"  Total Time in Bed: {total_mins:.0f} minutes")
            if "total_awake_time_milli" in stages and stages["total_awake_time_milli"] is not None:
                awake_mins = stages["total_awake_time_milli"] / 1000 / 60
                lines.append(f"  Awake Time: {awake_mins:.0f} minutes")
            if "total_light_sleep_time_milli" in stages and stages["total_light_sleep_time_milli"] is not None:
                light_mins = stages["total_light_sleep_time_milli"] / 1000 / 60
                lines.append(f"  Light Sleep: {light_mins:.0f} minutes")
            if "total_slow_wave_sleep_time_milli" in stages and stages["total_slow_wave_sleep_time_milli"] is not None:
                deep_mins = stages["total_slow_wave_sleep_time_milli"] / 1000 / 60
                lines.append(f"  Deep Sleep: {deep_mins:.0f} minutes")
            if "total_rem_sleep_time_milli" in stages and stages["total_rem_sleep_time_milli"] is not None:
                rem_mins = stages["total_rem_sleep_time_milli"] / 1000 / 60
                lines.append(f"  REM Sleep: {rem_mins:.0f} minutes")

    return "\n".join(lines)


def format_recovery(recovery: dict) -> str:
    """Format a recovery record into human-readable text."""
    lines = []

    # Header
    created = recovery.get("created_at", "")
    lines.append(f"Recovery: {created}")

    # Score data if available
    if recovery.get("score_state") == "SCORED" and "score" in recovery:
        score = recovery["score"]

        if "recovery_score" in score and score["recovery_score"] is not None:
            lines.append(f"  Recovery Score: {score['recovery_score']}%")
        if "resting_heart_rate" in score and score["resting_heart_rate"] is not None:
            lines.append(f"  Resting Heart Rate: {score['resting_heart_rate']} bpm")
        if "hrv_rmssd_milli" in score and score["hrv_rmssd_milli"] is not None:
            hrv = score["hrv_rmssd_milli"]
            lines.append(f"  HRV: {hrv:.1f} ms")
        if "spo2_percentage" in score and score["spo2_percentage"] is not None:
            lines.append(f"  SpO2: {score['spo2_percentage']}%")
        if "skin_temp_celsius" in score and score["skin_temp_celsius"] is not None:
            lines.append(f"  Skin Temperature: {score['skin_temp_celsius']:.1f}°C")

    return "\n".join(lines)


def format_cycle(cycle: dict) -> str:
    """Format a cycle record into human-readable text."""
    lines = []

    # Header
    start = cycle.get("start", "")
    end = cycle.get("end", "In Progress")
    lines.append(f"Cycle: {start} to {end}")

    # Score data if available
    if cycle.get("score_state") == "SCORED" and "score" in cycle:
        score = cycle["score"]

        if "strain" in score and score["strain"] is not None:
            lines.append(f"  Strain: {score['strain']}")
        if "kilojoule" in score and score["kilojoule"] is not None:
            lines.append(f"  Energy: {score['kilojoule']} kJ")
        if "average_heart_rate" in score and score["average_heart_rate"] is not None:
            lines.append(f"  Avg Heart Rate: {score['average_heart_rate']} bpm")
        if "max_heart_rate" in score and score["max_heart_rate"] is not None:
            lines.append(f"  Max Heart Rate: {score['max_heart_rate']} bpm")

    return "\n".join(lines)


def format_response(data: dict, formatter_func) -> str:
    """Format API response data using a specific formatter function."""
    if "records" in data:
        # Multiple records
        records = data["records"]
        if not records:
            return "No records found."

        formatted_records = [formatter_func(record) for record in records]
        result = "\n\n".join(formatted_records)

        # Add pagination info if available
        if "next_token" in data:
            result += "\n\n(More records available - use pagination)"

        return result
    else:
        # Single record or direct data
        return formatter_func(data)


@mcp.tool()
async def get_user_profile() -> str:
    """
    Get the authenticated WHOOP user's profile information.

    Returns basic profile data including user ID and account details.
    """
    client = get_client()
    profile = await client.get_user_profile()
    return json.dumps(profile, indent=2)


@mcp.tool()
async def get_recent_cycles(days: int = 7) -> str:
    """
    Get recent physiological cycles with recovery data.

    Args:
        days: Number of days to look back (default 7)

    Returns cycle data including strain, heart rate, and recovery scores.
    """
    client = get_client()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    cycles = await client.get_cycles(
        start_date=start_date.isoformat() + "Z",
        end_date=end_date.isoformat() + "Z"
    )
    return format_response(cycles, format_cycle)


@mcp.tool()
async def get_recent_recovery(days: int = 7) -> str:
    """
    Get recent recovery scores and metrics.

    Args:
        days: Number of days to look back (default 7)

    Returns recovery data including HRV, resting heart rate, and recovery percentage.
    """
    client = get_client()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    recovery = await client.get_recovery(
        start_date=start_date.isoformat() + "Z",
        end_date=end_date.isoformat() + "Z"
    )
    return format_response(recovery, format_recovery)


@mcp.tool()
async def get_recent_sleep(days: int = 7) -> str:
    """
    Get recent sleep data and metrics.

    Args:
        days: Number of days to look back (default 7)

    Returns sleep data including sleep stages, efficiency, and performance scores.
    """
    client = get_client()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    sleep = await client.get_sleep(
        start_date=start_date.isoformat() + "Z",
        end_date=end_date.isoformat() + "Z"
    )
    return format_response(sleep, format_sleep)


@mcp.tool()
async def get_recent_workouts(days: int = 7) -> str:
    """
    Get recent workout data and activities.

    Args:
        days: Number of days to look back (default 7)

    Returns workout data including sport type, strain, duration, and heart rate zones.
    """
    client = get_client()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    workouts = await client.get_workouts(
        start_date=start_date.isoformat() + "Z",
        end_date=end_date.isoformat() + "Z"
    )
    return format_response(workouts, format_workout)


@mcp.tool()
async def get_cycles_for_date_range(
    start_date: str,
    end_date: str,
    limit: int = 25
) -> str:
    """
    Get physiological cycles for a specific date range.

    Args:
        start_date: Start date in ISO 8601 format (e.g., "2024-01-01T00:00:00.000Z")
        end_date: End date in ISO 8601 format
        limit: Maximum number of records to return (default 25, max 50)

    Returns cycle data including strain, heart rate, and recovery scores.
    """
    client = get_client()
    cycles = await client.get_cycles(
        start_date=start_date,
        end_date=end_date,
        limit=min(limit, 50)  # Cap at 50
    )
    return format_response(cycles, format_cycle)


@mcp.tool()
async def get_sleep_for_date_range(
    start_date: str,
    end_date: str,
    limit: int = 25
) -> str:
    """
    Get sleep data for a specific date range.

    Args:
        start_date: Start date in ISO 8601 format (e.g., "2024-01-01T00:00:00.000Z")
        end_date: End date in ISO 8601 format
        limit: Maximum number of records to return (default 25, max 50)

    Returns sleep data including sleep stages, efficiency, and performance scores.
    """
    client = get_client()
    sleep = await client.get_sleep(
        start_date=start_date,
        end_date=end_date,
        limit=min(limit, 50)  # Cap at 50
    )
    return format_response(sleep, format_sleep)


@mcp.tool()
async def get_workouts_for_date_range(
    start_date: str,
    end_date: str,
    limit: int = 25
) -> str:
    """
    Get workout data for a specific date range.

    Args:
        start_date: Start date in ISO 8601 format (e.g., "2024-01-01T00:00:00.000Z")
        end_date: End date in ISO 8601 format
        limit: Maximum number of records to return (default 25, max 50)

    Returns workout data including sport type, strain, duration, and heart rate zones.
    """
    client = get_client()
    workouts = await client.get_workouts(
        start_date=start_date,
        end_date=end_date,
        limit=min(limit, 50)  # Cap at 50
    )
    return format_response(workouts, format_workout)


if __name__ == "__main__":
    mcp.run()
