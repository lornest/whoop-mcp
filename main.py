"""
WHOOP MCP Server

An MCP server that provides access to WHOOP API v2 data including:
- User profile information including body measurements (height, weight, max HR)
- Physiological cycles with recovery data
- Sleep data and metrics
- Workout data and activities

Requires OAuth 2.0 authentication.
"""

import os
import json
from datetime import datetime, timedelta
from fastmcp import FastMCP

from whoop_client import TokenManager, WhoopAPIClient
from formatters import (
    format_cycle,
    format_recovery,
    format_sleep,
    format_workout,
    format_response,
)

mcp = FastMCP("whoop-mcp")

# OAuth credentials (to be set via environment variables), see README.md for instructions
CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("WHOOP_ACCESS_TOKEN")
REFRESH_TOKEN = os.getenv("WHOOP_REFRESH_TOKEN")


def get_client() -> WhoopAPIClient:
    """Get an authenticated WHOOP API client."""
    if not ACCESS_TOKEN:
        raise ValueError(
            "WHOOP_ACCESS_TOKEN environment variable is not set. "
            "Please set it to your WHOOP API access token."
        )

    # Create token manager with refresh token support
    token_manager = TokenManager(
        ACCESS_TOKEN,
        REFRESH_TOKEN,
        CLIENT_ID,
        CLIENT_SECRET
    )
    return WhoopAPIClient(token_manager)


@mcp.tool(
    name="get_body_measurements",
    title="Get body measurements",
    description="Get the user's body measurements (height, weight, max HR)."
)
async def get_user_profile() -> str:
    """
    Get the authenticated WHOOP user's body measurements.

    Returns height (meters), weight (kilograms), and max heart rate.
    """
    client = get_client()
    profile = await client.get_user_profile()
    return json.dumps(profile, indent=2)


@mcp.tool(
    title="Get recent cycles",
    description="Get recent physiological cycles with recovery data. A cycle is a 'sleep-to-sleep' cycle, which is typically a day."
)
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


@mcp.tool(
    title="Get recent recovery",
    description="Get recent recovery scores and metrics. Recovery metrics include your recovery score, resting heart rate, HRV, blood oxygen saturation, and skin temperature."
)
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


@mcp.tool(
    title="Get recent sleep",
    description="Get recent sleep data and metrics. Sleep metrics include sleep stages, efficiency, and performance scores."
)
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


@mcp.tool(
    title="Get recent workouts",
    description="Get recent workout data and activities. Data includes sport type, strain, duration, and heart rate zones."
)
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


@mcp.tool(
    title="Get cycles for date range",
    description="Get physiological cycles for a specific date range."
)
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


@mcp.tool(
    title="Get sleep for date range",
    description="Get sleep data for a specific date range."
)
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


@mcp.tool(
    title="Get workouts for date range",
    description="Get workout data for a specific date range."
)
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
