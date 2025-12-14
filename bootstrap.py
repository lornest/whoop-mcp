#!/usr/bin/env python3
"""
WHOOP MCP Server Bootstrap Script

This script helps you set up the WHOOP MCP server for use with Claude Code
or other MCP clients. It completes the OAuth 2.0 flow and outputs the
complete configuration ready to add to your MCP client.

Usage:
    python oauth_helper.py

Requirements:
    - Set WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET in .env file
    - Configure redirect URI in WHOOP Developer Dashboard as: http://localhost:8080/callback
"""

import json
import os
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import load_dotenv

from secure_token_storage import TokenData, get_storage_backend

load_dotenv()

CLIENT_ID = os.getenv("WHOOP_CLIENT_ID")
CLIENT_SECRET = os.getenv("WHOOP_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8080/callback"
AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

# Scopes needed for the Whoop API (note: we need offline access to refresh the token!)
SCOPES = "read:body_measurement read:cycles read:recovery read:sleep read:workout offline"

# State for CSRF protection
STATE = secrets.token_urlsafe(32)

auth_code = None
auth_error = None


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callback."""

    def do_GET(self):
        """Handle GET request to callback endpoint."""
        global auth_code, auth_error

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/callback":
            if "error" in params:
                auth_error = params["error"][0]
                error_desc = params.get("error_description", ["Unknown error"])[0]

                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(f"""
                    <html>
                    <head><title>Authorization Failed</title></head>
                    <body>
                        <h1>Authorization Failed</h1>
                        <p>Error: {auth_error}</p>
                        <p>Description: {error_desc}</p>
                        <p>You can close this window.</p>
                    </body>
                    </html>
                """.encode())
                return

            returned_state = params.get("state", [None])[0]
            if returned_state != STATE:
                auth_error = "Invalid state parameter (CSRF protection)"

                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html>
                    <head><title>Authorization Failed</title></head>
                    <body>
                        <h1>Authorization Failed</h1>
                        <p>Invalid state parameter. Possible CSRF attack.</p>
                        <p>You can close this window.</p>
                    </body>
                    </html>
                """)
                return

            auth_code = params.get("code", [None])[0]

            if auth_code:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html>
                    <head><title>Authorization Successful</title></head>
                    <body>
                        <h1>Authorization Successful!</h1>
                        <p>You have successfully authorized the WHOOP MCP server.</p>
                        <p>The access token is being retrieved...</p>
                        <p>You can close this window.</p>
                    </body>
                    </html>
                """)
            else:
                auth_error = "No authorization code received"
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                    <html>
                    <head><title>Authorization Failed</title></head>
                    <body>
                        <h1>Authorization Failed</h1>
                        <p>No authorization code received from WHOOP.</p>
                        <p>You can close this window.</p>
                    </body>
                    </html>
                """)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress HTTP server logs."""
        pass


def exchange_code_for_token(code: str) -> dict:
    """Exchange authorization code for access token."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
    }

    response = httpx.post(TOKEN_URL, data=data)
    response.raise_for_status()
    return response.json()


def main():
    """Run the OAuth flow."""
    global auth_code, auth_error

    if not CLIENT_ID or not CLIENT_SECRET:
        print("❌ Error: WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET must be set in .env file")
        print("\nPlease:")
        print("1. Copy .env.example to .env")
        print("2. Add your Client ID and Client Secret from https://developer-dashboard.whoop.com")
        return

    print("WHOOP OAuth Helper")
    print("=" * 60)
    print("\n📋 Configuration:")
    print(f"   Client ID: {CLIENT_ID[:8]}...")
    print(f"   Redirect URI: {REDIRECT_URI}")
    print(f"   Scopes: {SCOPES}")

    print("\n⚙️  Make sure your WHOOP Developer Dashboard has this redirect URI:")
    print(f"   {REDIRECT_URI}")
    print()

    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": STATE,
    }
    authorization_url = f"{AUTH_URL}?{urlencode(auth_params)}"

    print("🔄 Starting local server on http://localhost:8080...")
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    print("✅ Server ready to receive OAuth callback")
    print()

    print("🌐 Opening authorization URL in your browser...")
    print("   If it doesn't open automatically, visit:")
    print(f"   {authorization_url}")
    print()

    webbrowser.open(authorization_url)

    print("   Waiting for authorization...")
    print()

    while auth_code is None and auth_error is None:
        server.handle_request()

    if auth_error:
        print(f"❌ Authorization failed: {auth_error}")
        return

    if not auth_code:
        print("❌ No authorization code received")
        return

    print("✅ Authorization code received!")
    print()

    print("🔄 Exchanging authorization code for access token...")
    try:
        token_response = exchange_code_for_token(auth_code)

        access_token = token_response.get("access_token")
        refresh_token = token_response.get("refresh_token")
        expires_in = token_response.get("expires_in")

        print("✅ Success! Access token received.")
        print()
        print("=" * 60)
        print("Your Access Token:")
        print("=" * 60)
        print(access_token)
        print("=" * 60)
        print()

        if refresh_token:
            print("Refresh Token (for long-term access):")
            print("=" * 60)
            print(refresh_token)
            print("=" * 60)
            print()

        print(f"Token expires in: {expires_in} seconds ({expires_in // 3600} hours)")
        print()

        token_data = TokenData(
            access_token=access_token,
            refresh_token=refresh_token,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            expires_at=time.time() + expires_in if expires_in else None,
            created_at=time.time()
        )

        storage = get_storage_backend()
        storage.save_tokens(token_data)
        print("✅ Tokens saved to secure storage (OS keychain or encrypted file)")
        print()

        script_dir = Path(__file__).parent.resolve()

        mcp_config = {
            "whoop": {
                "command": "uv",
                "args": [
                    "--directory",
                    str(script_dir),
                    "run",
                    "main.py"
                ]
            }
        }

        print("=" * 80)
        print("🎉 MCP SERVER CONFIGURATION")
        print("=" * 80)
        print()
        print("Copy the configuration below and add it to your MCP client config:")
        print()
        print("For Claude Code/Claude Desktop:")
        print("  • macOS: ~/Library/Application Support/Claude/claude_desktop_config.json")
        print("  • Windows: %APPDATA%/Claude/claude_desktop_config.json")
        print()
        print("Add this to the 'mcpServers' section:")
        print()
        print(json.dumps(mcp_config, indent=2))
        print()
        print("=" * 80)
        print()
        print("✅ Once you have added the configuration to your MCP client, restart Claude Code to use your WHOOP MCP server.")

    except Exception as e:
        print(f"❌ Failed to exchange code for token: {e}")
        return


if __name__ == "__main__":
    main()
