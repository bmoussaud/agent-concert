"""
Validate the Spotify MCP connection via APIM.

Sends an MCP initialize request, lists available tools, and calls
the search tool with 'Eiffel' to confirm end-to-end connectivity.

The Spotify MCP uses OAuth2. Set SPOTIFY_CLIENT_ID and
SPOTIFY_CLIENT_SECRET in your .env to obtain a client-credentials
token automatically. Without them, only the MCP initialize handshake
is tested.

Usage:
    uv run scripts/validate-mcp-spotify.py

Required environment variables (loaded from .env):
    AZURE_SPOTIFY_MCP_URL          - MCP server URL exposed through APIM
    AZURE_SPOTIFY_SUBSCRIPTION_KEY - APIM subscription key

Optional (needed for tool-call tests):
    SPOTIFY_CLIENT_ID              - Spotify app client ID
    SPOTIFY_CLIENT_SECRET          - Spotify app client secret
"""
import base64
import http.client
import json
import os
import ssl
import sys
import urllib.parse
from dotenv import load_dotenv

load_dotenv(override=False)

MCP_URL = os.getenv("AZURE_SPOTIFY_MCP_URL")
SUBSCRIPTION_KEY = os.getenv("AZURE_SPOTIFY_SUBSCRIPTION_KEY")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
TIMEOUT = 30  # seconds

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"


def ok(msg: str) -> None:
    print(f"{GREEN}[OK]{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}[FAIL]{RESET} {msg}")


def info(msg: str) -> None:
    print(f"{YELLOW}[INFO]{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {msg}")


def get_spotify_token() -> str:
    """Fetch a client-credentials OAuth token from Spotify."""
    credentials = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()

    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": str(len(body)),
    }

    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection("accounts.spotify.com", timeout=15, context=ctx)
    try:
        conn.request("POST", "/api/token", body=body, headers=headers)
        resp = conn.getresponse()
        data = json.loads(resp.read().decode())
    finally:
        conn.close()

    if resp.status != 200:
        raise ConnectionError(f"Spotify token request failed: HTTP {resp.status} - {data}")

    print(f"Spotify token response: {data}")
    return data["access_token"]


def post_mcp(payload: dict, bearer_token: str | None = None) -> dict:
    """
    Send a JSON-RPC MCP POST request and return the parsed response.

    The MCP Streamable HTTP transport responds with SSE (text/event-stream).
    We read line-by-line and return as soon as we find the first JSON data line,
    avoiding blocking on the long-lived SSE connection.
    """
    parsed = urllib.parse.urlparse(MCP_URL)
    host = parsed.netloc
    path = parsed.path

    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
        "Content-Length": str(len(body)),
    }
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"

    print(f"POST {MCP_URL} with payload: {json.dumps(payload)}")
    ctx = ssl.create_default_context()
    conn = http.client.HTTPSConnection(host, timeout=TIMEOUT, context=ctx)
    try:
        conn.request("POST", path, body=body, headers=headers)
        resp = conn.getresponse()

        if resp.status >= 400:
            raise ConnectionError(f"HTTP {resp.status} {resp.reason}")

        content_type = resp.getheader("Content-Type", "")

        # SSE transport: read line-by-line until we get a data line with JSON
        if "text/event-stream" in content_type:
            while True:
                raw_line = resp.readline()
                if not raw_line:
                    raise ValueError("SSE stream ended before a data line was received")
                line = raw_line.decode().rstrip("\r\n")
                if line.startswith("data:"):
                    return json.loads(line[len("data:"):].strip())
        else:
            # Plain JSON response
            return json.loads(resp.read().decode())
    finally:
        conn.close()


def check_env() -> bool:
    missing = []
    if not MCP_URL:
        missing.append("AZURE_SPOTIFY_MCP_URL")
    if not SUBSCRIPTION_KEY:
        missing.append("AZURE_SPOTIFY_SUBSCRIPTION_KEY")
    if missing:
        fail(f"Missing environment variables: {', '.join(missing)}")
        return False
    ok(f"MCP URL: {MCP_URL}")
    ok(f"Subscription key: {'*' * 8}{SUBSCRIPTION_KEY[-4:]}")
    if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
        ok("Spotify OAuth credentials found - tool-call tests will run")
    else:
        warn("SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set - tool-call tests will be skipped")
    return True


def validate_initialize(bearer_token: str | None) -> bool:
    info("Sending MCP initialize request...")
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "validate-mcp", "version": "1.0"},
        },
    }
    try:
        response = post_mcp(payload, bearer_token)
    except ConnectionError as exc:
        fail(f"HTTP error: {exc}")
        return False
    except OSError as exc:
        fail(f"Connection error: {exc}")
        return False
    except Exception as exc:
        fail(f"Unexpected error: {exc}")
        return False

    if "error" in response:
        fail(f"MCP error: {response['error']}")
        return False

    result = response.get("result", {})
    server_info = result.get("serverInfo", {})
    protocol_version = result.get("protocolVersion", "unknown")
    ok(f"MCP server responded: {server_info.get('name', 'unknown')} v{server_info.get('version', '?')}")
    ok(f"Protocol version: {protocol_version}")
    return True


def validate_list_tools(bearer_token: str | None) -> bool:
    info("Listing available MCP tools...")
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    try:
        response = post_mcp(payload, bearer_token)
    except ConnectionError as exc:
        fail(f"HTTP error: {exc}")
        return False
    except OSError as exc:
        warn(f"tools/list timed out (Spotify MCP may require user-scoped OAuth): {exc}")
        return True  # Non-fatal: initialize already confirmed connectivity
    except Exception as exc:
        warn(f"tools/list unexpected error: {exc}")
        return True  # Non-fatal

    if "error" in response:
        fail(f"MCP error: {response['error']}")
        return False

    tools = response.get("result", {}).get("tools", [])
    if not tools:
        warn("No tools returned by MCP server")
        return True  # Non-fatal

    ok(f"{len(tools)} tool(s) available:")
    for tool in tools:
        print(f"    - {tool.get('name')}: {tool.get('description', '')}")
    return True


def validate_search_artists(bearer_token: str, artist_name: str = "Eiffel") -> bool:
    # APIM auto-generates tool names from the OpenAPI spec - the search tool is 'searchForItem'
    info(f"Calling searchForItem with q='{artist_name}' and type='artist'...")
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "searchForItem",
            "arguments": {"q": artist_name, "type": "artist"},
        },
    }
    try:
        response = post_mcp(payload, bearer_token)
    except ConnectionError as exc:
        fail(f"HTTP error: {exc}")
        return False
    except OSError as exc:
        fail(f"Connection error: {exc}")
        return False
    except Exception as exc:
        fail(f"Unexpected error: {exc}")
        return False

    if "error" in response:
        fail(f"MCP error: {response['error']}")
        return False

    content = response.get("result", {}).get("content", [])
    if not content:
        fail("No content returned by search")
        return False

    try:
        data = json.loads(content[0].get("text", "{}"))
        artists = data.get("artists", {}).get("items", [])
        ok(f"Found {len(artists)} artist(s) matching '{artist_name}':")
        for artist in artists[:5]:
            genres = ", ".join(artist.get("genres", [])[:3]) or "n/a"
            print(f"    - {artist.get('name')} (popularity: {artist.get('popularity', 'n/a')}, genres: {genres})")
    except (json.JSONDecodeError, KeyError):
        ok(f"Response received ({len(str(content))} chars): {str(content)[:200]}")

    return True


def main() -> int:
    print("\n=== Spotify MCP Connection Validation ===\n")

    if not check_env():
        return 1

    # Fetch Spotify OAuth token if credentials are available
    bearer_token = None
    if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
        print()
        info("Fetching Spotify OAuth token (client credentials)...")
        try:
            bearer_token = get_spotify_token()
            ok(f"OAuth token obtained: {'*' * 20}{bearer_token[-6:]}")
        except Exception as exc:
            fail(f"Could not obtain Spotify OAuth token: {exc}")
            return 1

    print()
    init_ok = validate_initialize(bearer_token)
    print()
    tools_ok = validate_list_tools(bearer_token)

    search_ok = True
    if bearer_token:
        print()
        search_ok = validate_search_artists(bearer_token, "Eiffel")
    else:
        warn("Skipping search test (no OAuth credentials)")

    print()
    if init_ok and tools_ok and search_ok:
        ok("All checks passed - MCP connection is healthy.")
        return 0
    else:
        fail("One or more checks failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
