# WHOOP MCP Server

An MCP (Model Context Protocol) server that provides seamless access to your WHOOP fitness and recovery data through Claude and other MCP clients.

Built for **WHOOP API v2**.

## Features

Access your WHOOP data naturally through conversation:

- **Body Measurements**: Height, weight, and max heart rate
- **Physiological Cycles**: Strain scores and heart rate metrics
- **Recovery Data**: Recovery scores, HRV, resting heart rate, SpO2, and skin temperature
- **Sleep Analysis**: Sleep stages, efficiency, performance scores, and sleep quality
- **Workout Tracking**: Activities with sport types, strain, duration, heart rate zones, and distance
- **Automatic Token Refresh**: No manual re-authentication needed - refresh tokens handle everything

## Prerequisites

- Python 3.12+
- A WHOOP account with an active membership
- Access to the [WHOOP Developer Dashboard](https://developer-dashboard.whoop.com) - just login with your WHOOP account!

## Quick Start

### 1. Install Dependencies

This project uses `uv` for dependency management. If you don't have it installed:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then sync dependencies:

```bash
uv sync
```

### 2. Create a WHOOP OAuth Application

1. Visit the [WHOOP Developer Dashboard](https://developer-dashboard.whoop.com)
2. Create a new application (or use an existing one)
3. **Configure the redirect URI:** `http://localhost:8080/callback`
4. For contacts add your email address and privacy policy URL just use https://example.com/privacy, this is only for your usage!
5. Select all scopes
6. Note your **Client ID** and **Client Secret**

### 3. Run the Bootstrap Script

Create a `.env` file with your OAuth application credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
WHOOP_CLIENT_ID=your_client_id_here
WHOOP_CLIENT_SECRET=your_client_secret_here
```

Run the bootstrap script:

```bash
python oauth_helper.py
```

This will:
1. Open your browser to authorize the application
2. Start a local web server to receive the OAuth callback
3. Exchange the authorization code for access and refresh tokens
4. **Output the complete MCP server configuration** ready to copy

### 4. Add to Your MCP Client

The bootstrap script outputs a configuration block. Copy it and add it to your MCP client:

**For Claude Desktop:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

The configuration will look like this:

```json
{
  "mcpServers": {
    "whoop": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/whoop-mcp",
        "run",
        "main.py"
      ],
      "env": {
        "WHOOP_CLIENT_ID": "your_client_id",
        "WHOOP_CLIENT_SECRET": "your_client_secret",
        "WHOOP_ACCESS_TOKEN": "your_access_token",
        "WHOOP_REFRESH_TOKEN": "your_refresh_token"
      }
    }
  }
}
```

**Restart Claude Desktop** and you're ready to use the WHOOP MCP server!

---

## Advanced Configuration

### Manual Testing (Without MCP Client)

To run the server standalone for testing:

```bash
uv run main.py
```

### Manual OAuth Flow

If you prefer to handle OAuth manually instead of using the bootstrap script:

**Authorization URL:** `https://api.prod.whoop.com/oauth/oauth2/auth`

**Token URL:** `https://api.prod.whoop.com/oauth/oauth2/token`

**Required Scopes:** `read:profile read:cycles read:recovery read:sleep read:workout offline`

For detailed OAuth setup, see the [WHOOP OAuth documentation](https://developer.whoop.com/docs/developing/oauth).

### Alternative: .env File Configuration

For local development/testing, you can use environment variables in a `.env` file:

```env
WHOOP_CLIENT_ID=your_client_id
WHOOP_CLIENT_SECRET=your_client_secret
WHOOP_ACCESS_TOKEN=your_access_token
WHOOP_REFRESH_TOKEN=your_refresh_token
```

Then run: `uv run main.py`

## What Can You Ask?

Once configured, you can interact with your WHOOP data naturally through Claude:

- "What was my recovery score this morning?"
- "Show me my sleep data for the last week"
- "How many workouts did I do this month?"
- "What's my average HRV over the past 30 days?"
- "Did I get enough deep sleep last night?"
- "What was the strain on my last run?"
- "What are my body measurements?"

## Available Tools

### get_user_profile()
Get the authenticated user's body measurements including:
- Height (meters)
- Weight (kilograms)
- Max heart rate (bpm)

### get_recent_cycles(days=7)
Get physiological cycles for the last N days (default 7).

**Parameters:**
- `days` (int): Number of days to look back

**Returns:** Cycle data with strain, heart rate, and recovery scores

### get_recent_recovery(days=7)
Get recovery data for the last N days.

**Parameters:**
- `days` (int): Number of days to look back

**Returns:** Recovery scores, HRV, resting heart rate, SpO2, and skin temperature

### get_recent_sleep(days=7)
Get sleep data for the last N days.

**Parameters:**
- `days` (int): Number of days to look back

**Returns:** Sleep stages, efficiency, performance, sleep need, and respiratory rate

### get_recent_workouts(days=7)
Get workout data for the last N days.

**Parameters:**
- `days` (int): Number of days to look back

**Returns:** Workout activities with sport type, strain, duration, and heart rate zones

### get_cycles_for_date_range(start_date, end_date, limit=25)
Get cycles for a specific date range.

**Parameters:**
- `start_date` (str): ISO 8601 formatted date (e.g., "2024-01-01T00:00:00.000Z")
- `end_date` (str): ISO 8601 formatted date
- `limit` (int): Max records to return (default 25, max 50)

### get_sleep_for_date_range(start_date, end_date, limit=25)
Get sleep data for a specific date range.

**Parameters:**
- `start_date` (str): ISO 8601 formatted date
- `end_date` (str): ISO 8601 formatted date
- `limit` (int): Max records to return (default 25, max 50)

### get_workouts_for_date_range(start_date, end_date, limit=25)
Get workout data for a specific date range.

**Parameters:**
- `start_date` (str): ISO 8601 formatted date
- `end_date` (str): ISO 8601 formatted date
- `limit` (int): Max records to return (default 25, max 50)

## API Version

This server uses **WHOOP API v2**. Note that v1 of the WHOOP API will be discontinued on **October 1, 2025**.

## Data Types

### Cycle
Represents a physiological cycle (not a calendar day) with:
- Start and end times
- Strain score and kilojoules
- Average and max heart rate
- Recovery data (when available)

### Recovery
Daily readiness metrics including:
- Recovery percentage (0-100)
- HRV RMSSD (ms)
- Resting heart rate (bpm)
- SpO2 percentage (WHOOP 4.0 only)
- Skin temperature (Celsius)

### Sleep
Sleep session data with:
- Sleep stages (light, deep/slow-wave, REM, awake)
- Sleep performance and efficiency percentages
- Sleep need calculations
- Respiratory rate
- Disturbance count

### Workout
Exercise activity data including:
- Sport name and ID (100+ supported activities)
- Strain score
- Duration and distance
- Heart rate zones (5 levels)
- Altitude and kilojoules

## Automatic Token Refresh

WHOOP access tokens are short-lived (typically a few hours). This server automatically handles token refresh:

1. **When a token expires** (401 error), the server automatically uses the refresh token to get a new access token
2. **No manual intervention required** - The process is seamless and transparent
3. **Refresh tokens are long-lived** - They typically last much longer (weeks/months)
4. **Important:** Always include the `WHOOP_REFRESH_TOKEN` in your configuration

**How it works:**
- The server detects when an access token has expired
- It automatically calls the WHOOP token refresh endpoint
- Updates the access token in memory
- Retries the original request with the new token
- All of this happens transparently without user intervention

If token refresh fails, you'll need to re-authenticate using `python oauth_helper.py`.

## Error Handling

The server includes comprehensive error handling:
- Missing access token will raise a clear error message
- Expired tokens are automatically refreshed using the refresh token
- HTTP errors from the WHOOP API will be propagated with helpful messages
- Rate limit errors (429) are clearly identified
- Network errors are caught and reported
- Invalid date ranges will be handled by the API

## Rate Limiting

WHOOP API has rate limits. If you encounter rate limiting errors:
- Reduce the frequency of requests
- Use date range queries instead of multiple recent queries
- Implement caching for frequently accessed data
- The server will report rate limit errors clearly

## Contributing

Contributions are welcome! Please ensure:
- Code follows the existing style
- New features include docstrings
- Error handling is appropriate

## License

This project is provided as-is for use with the WHOOP API v2.

## Resources

- [WHOOP Developer Portal](https://developer.whoop.com)
- [WHOOP API Documentation](https://developer.whoop.com/docs/introduction)
- [WHOOP Developer Dashboard](https://developer-dashboard.whoop.com)
- [OAuth 2.0 Guide](https://developer.whoop.com/docs/developing/oauth)
- [MCP Documentation](https://modelcontextprotocol.io)
