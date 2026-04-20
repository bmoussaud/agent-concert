"""
Validate the setlist.fm MCP connection via APIM.

Sends an MCP initialize request and lists available tools to confirm
the MCP server is reachable and responding correctly.

Usage:
    uv run scripts/validate-mcp-setlistfm.py

Required environment variables (loaded from .env):
    AZURE_SETLISTFM_MCP_URL        - MCP server URL exposed through APIM
    AZURE_SETLISTFM_SUBSCRIPTION_KEY - APIM subscription key
"""
import http.client
import json
import os
import ssl
import sys
import urllib.parse
from dotenv import load_dotenv

load_dotenv(override=False)

MCP_URL = os.getenv("AZURE_SETLISTFM_MCP_URL")
SUBSCRIPTION_KEY = os.getenv("AZURE_SETLISTFM_SUBSCRIPTION_KEY")
TIMEOUT = 20  # seconds

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


def post_mcp(payload: dict) -> dict:
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
        missing.append("AZURE_SETLISTFM_MCP_URL")
    if not SUBSCRIPTION_KEY:
        missing.append("AZURE_SETLISTFM_SUBSCRIPTION_KEY")
    if missing:
        fail(f"Missing environment variables: {', '.join(missing)}")
        return False
    ok(f"MCP URL: {MCP_URL}")
    ok(f"Subscription key: {'*' * 8}{SUBSCRIPTION_KEY[-4:]}")
    return True


def validate_initialize() -> bool:
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
        response = post_mcp(payload)
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


def validate_list_tools() -> bool:
    info("Listing available MCP tools...")
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    try:
        response = post_mcp(payload)
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

    tools = response.get("result", {}).get("tools", [])
    if not tools:
        fail("No tools returned by MCP server")
        return False

    ok(f"{len(tools)} tool(s) available:")
    for tool in tools:
        print(f"    - {tool.get('name')}: {tool.get('description', '')}")
    return True


def validate_search_artists(artist_name: str = "Eiffel") -> bool:
    info(f"Calling searchForArtists with artistName='{artist_name}'...")
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "searchForArtists",
            "arguments": {"artistName": artist_name},
        },
    }
    try:
        response = post_mcp(payload)
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
        fail("No content returned by searchForArtists")
        return False

    # Parse the returned text as JSON to display artist names
    try:
        data = json.loads(content[0].get("text", "{}"))
        artists = data.get("artist", [])
        ok(f"Found {len(artists)} artist(s) matching '{artist_name}':")
        for artist in artists[:5]:
            print(f"    - {artist.get('name')} (mbid: {artist.get('mbid', 'n/a')})")
    except (json.JSONDecodeError, KeyError):
        # Fall back to raw text preview
        ok(f"Response received ({len(str(content))} chars): {str(content)[:200]}")

    return True


def main() -> int:
    print("\n=== setlist.fm MCP Connection Validation ===\n")

    if not check_env():
        return 1

    print()
    init_ok = validate_initialize()
    print()
    tools_ok = validate_list_tools()
    print()
    search_ok = validate_search_artists("Eiffel")
    print()

    if init_ok and tools_ok and search_ok:
        ok("All checks passed - MCP connection is healthy.")
        return 0
    else:
        fail("One or more checks failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
