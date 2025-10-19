# WHOOP MCP Server

An MCP (Model Context Protocol) server that provides access to WHOOP API v2 data for wearable device metrics.

## Features

This MCP server provides tools to access:

- **User Profile**: Get authenticated user's basic profile information
- **Physiological Cycles**: Access cycle data with strain and heart rate metrics
- **Recovery Data**: Retrieve recovery scores, HRV, resting heart rate, and readiness metrics
- **Sleep Data**: Get sleep stages, efficiency, performance scores, and sleep quality metrics
- **Workout Data**: Access workout activities with sport types, strain, duration, and heart rate zones
- **Automatic Token Refresh**: Seamlessly refreshes expired access tokens using refresh tokens without manual intervention

## Prerequisites

- Python 3.12 or higher
- A WHOOP account
- WHOOP Developer Dashboard access at [developer-dashboard.whoop.com](https://developer-dashboard.whoop.com)

## Setup

### 1. Install Dependencies

This project uses `uv` for dependency management:

```bash
uv sync
```

Or with pip:

```bash
pip install fastmcp httpx
```

### 2. Configure WHOOP API Credentials

1. Visit the [WHOOP Developer Dashboard](https://developer-dashboard.whoop.com)
2. Create a new application or use an existing one
3. Note your Client ID and Client Secret
4. Configure your OAuth 2.0 redirect URI

5. Copy the example environment file:

```bash
cp .env.example .env
```

6. Edit `.env` and add your credentials (you'll get the tokens in the next step):

```env
WHOOP_CLIENT_ID=your_client_id
WHOOP_CLIENT_SECRET=your_client_secret
WHOOP_ACCESS_TOKEN=your_access_token
WHOOP_REFRESH_TOKEN=your_refresh_token
```

### 3. Configure OAuth Redirect URI in WHOOP Developer Dashboard

**Important:** Before getting your access token, configure the redirect URI:

1. Go to [WHOOP Developer Dashboard](https://developer-dashboard.whoop.com)
2. Select your application
3. Add this redirect URI: `http://localhost:8080/callback`
4. Save the changes

### 4. Obtain an Access Token

Use the included OAuth helper script to get your access token:

```bash
python oauth_helper.py
```

This will:
1. Open your browser to authorize the application
2. Start a local web server to receive the callback
3. Exchange the authorization code for an access token
4. Display your access token and refresh token

Then copy **both** the access token and refresh token to your `.env` file:

```env
WHOOP_ACCESS_TOKEN=your_access_token_here
WHOOP_REFRESH_TOKEN=your_refresh_token_here
```

**Important:** WHOOP access tokens are short-lived. The refresh token is essential for the server to automatically refresh expired tokens without manual re-authentication.

**Manual OAuth Flow (Alternative):**

If you prefer to do it manually:

**Authorization URL:**
```
https://api.prod.whoop.com/oauth/oauth2/auth
```

**Token URL:**
```
https://api.prod.whoop.com/oauth/oauth2/token
```

**Required Scopes:**
```
read:profile read:cycles read:recovery read:sleep read:workout offline
```

**Required Parameters:**
- `client_id` - Your Client ID
- `redirect_uri` - `http://localhost:8080/callback` (or your configured URI)
- `response_type` - `code`
- `scope` - The scopes listed above
- `state` - Random string for CSRF protection (min 8 characters)

For detailed OAuth setup, see the [WHOOP OAuth documentation](https://developer.whoop.com/docs/developing/oauth).

## Running the Server

### As an MCP Server

Run the server using FastMCP:

```bash
uv run main.py
```

Or with Python:

```bash
python main.py
```

### Configuration for Claude Desktop

Add this to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "whoop": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/YOUR_USERNAME/path/to/whoop-mcp",
        "run",
        "main.py"
      ],
      "env": {
        "WHOOP_CLIENT_ID": "your_client_id_here",
        "WHOOP_CLIENT_SECRET": "your_client_secret_here",
        "WHOOP_ACCESS_TOKEN": "your_access_token_here",
        "WHOOP_REFRESH_TOKEN": "your_refresh_token_here"
      }
    }
  }
}
```

**Important notes:**
- Replace `/Users/YOUR_USERNAME/path/to/whoop-mcp` with the actual absolute path to this project
- Include **all four** environment variables (especially the refresh token for automatic token renewal)
- The `--directory` flag tells `uv` where to find the project and its dependencies

## Available Tools

### get_user_profile()
Get the authenticated user's basic profile information.

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

## Example Usage

Once configured in Claude Desktop, you can ask questions like:

- "What was my recovery score yesterday?"
- "Show me my sleep data for the last week"
- "What workouts did I do this month?"
- "How has my HRV been trending over the past 30 days?"

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
