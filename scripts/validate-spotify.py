"""
Validate the Spotify agent end-to-end via Azure AI Foundry.

Creates a 'validate-spotify' agent against the Azure AI Foundry project,
then runs a single-turn conversation searching for an artist on Spotify
and validates that the response contains music-related content.

Usage:
    uv run scripts/validate-spotify.py [search_query]

    search_query defaults to "Radiohead" when not supplied.

Required environment variables (loaded from .env):
    AZURE_AI_PROJECT_ENDPOINT          - Azure AI Foundry project endpoint
    AZURE_AI_MODEL_DEPLOYMENT_NAME     - Model deployment name
    AZURE_SPOTIFY_MCP_URL              - MCP server URL exposed through APIM

Note:
    Authentication is handled via the 'apikey-spotify-mcp-connection' project
    connection defined in Azure AI Foundry.
"""
import os
import sys
from dotenv import load_dotenv

# Load .env before importing Azure SDK so env vars are available
load_dotenv(override=False)

from azure.identity import DefaultAzureCredential  # noqa: E402
from azure.ai.projects import AIProjectClient  # noqa: E402
from azure.ai.projects.models import MCPTool, PromptAgentDefinition  # noqa: E402

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Validation steps
# ---------------------------------------------------------------------------

def check_env() -> bool:
    """Validate that all required environment variables are present."""
    required = {
        "AZURE_AI_PROJECT_ENDPOINT": os.getenv("AZURE_AI_PROJECT_ENDPOINT"),
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
        "AZURE_SPOTIFY_MCP_URL": os.getenv("AZURE_SPOTIFY_MCP_URL"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        fail(f"Missing environment variables: {', '.join(missing)}")
        return False
    ok(f"Project endpoint:  {required['AZURE_AI_PROJECT_ENDPOINT']}")
    ok(f"Model deployment:  {required['AZURE_AI_MODEL_DEPLOYMENT_NAME']}")
    ok(f"MCP URL:           {required['AZURE_SPOTIFY_MCP_URL']}")
    ok("Auth:              apikey-spotify-mcp-connection (project connection)")

    return True


def create_project_client() -> AIProjectClient:
    """Create an AIProjectClient using DefaultAzureCredential."""
    credential = DefaultAzureCredential()
    return AIProjectClient(
        credential=credential,
        endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT"),
    )


def create_agent(client: AIProjectClient) -> tuple[str, str]:
    """
    Create the 'validate-spotify' agent in Azure AI Foundry.

    Returns:
        (agent_name, agent_version) tuple.
    """
    instructions = (
        "You are a music research assistant. "
        "You have access to the Spotify API through Azure API Management, which allows you to "
        "search for artists, albums, tracks, and playlists. "
        "When asked to search for an artist or music, use the searchForItem tool with the "
        "appropriate query and type. "
        "Return results clearly, including the artist name, popularity, and genres where available."
    )

    mcp_tool = MCPTool(
        server_label="agent-mcp-spotify",
        server_url=os.getenv("AZURE_SPOTIFY_MCP_URL"),
        require_approval="never",
        project_connection_id="apikey-spotify-mcp-connection",
    )

    with client.get_openai_client():
        agent = client.agents.create_version(
            agent_name="validate-spotify",
            definition=PromptAgentDefinition(
                model=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
                instructions=instructions,
                tools=[mcp_tool],
            ),
        )
    return agent.name, agent.version


def run_turn(client: AIProjectClient, agent_name: str, agent_version: str, history: list[dict]) -> str | None:
    """
    Send one conversation turn to the agent and return its text response.

    Args:
        client:        Initialised AIProjectClient.
        agent_name:    Agent name returned by create_version.
        agent_version: Agent version returned by create_version.
        history:       Full conversation history (mutated in place by caller).

    Returns:
        The agent's output_text on success, or None on failure.
    """
    with client.get_openai_client() as openai_client:
        response = openai_client.responses.create(
            input=history,
            extra_body={
                "agent_reference": {
                    "name": agent_name,
                    "version": agent_version,
                    "type": "agent_reference",
                }
            },
        )
    if response.status != "completed":
        fail(f"Agent run ended with unexpected status: {response.status}")
        return None
    return response.output_text


def validate_create_agent(
    client: AIProjectClient,
) -> tuple[str, str] | tuple[None, None]:
    """Create the validate-spotify agent and report the result."""
    info("Creating 'validate-spotify' agent...")
    try:
        agent_name, agent_version = create_agent(client)
        ok(f"Agent created: name={agent_name!r}, version={agent_version!r}")
        return agent_name, agent_version
    except Exception as exc:
        fail(f"Failed to create agent: {exc}")
        return None, None


def validate_search_query(
    client: AIProjectClient,
    agent_name: str,
    agent_version: str,
    query: str,
    history: list[dict],
) -> bool:
    """
    Single turn – ask the agent to search Spotify for the given query.

    Appends the user message and assistant reply to *history*.
    Validates that the response contains music-related keywords.
    """
    user_msg = f"Search Spotify for the artist '{query}' and tell me about the results"
    info(f"Turn 1 — user: {user_msg!r}")
    history.append({"role": "user", "content": user_msg})

    try:
        reply = run_turn(client, agent_name, agent_version, history)
    except Exception as exc:
        fail(f"Agent call failed: {exc}")
        return False

    if not reply:
        fail("Agent returned an empty response for the search query")
        return False

    info(f"Turn 1 — agent reply (first 600 chars):\n{reply[:600]}")

    # Basic content check: response should mention music-related keywords
    keywords = ("artist", "spotify", "music", "genre", "album", "track", "popularity", "band", "song")
    reply_lower = reply.lower()
    if not any(kw in reply_lower for kw in keywords):
        fail("Response does not appear to contain Spotify search data")
        return False

    ok(f"Spotify search results received and validated for query {query!r}")
    history.append({"role": "assistant", "content": reply})
    return True


def validate_query_albums(
    client: AIProjectClient,
    agent_name: str,
    agent_version: str,
    query: str,
    history: list[dict],
) -> bool:
    """
    Turn 2 – ask the agent to list albums for the artist found in Turn 1.

    Appends the user message and assistant reply to *history*.
    Validates that the response contains album-related keywords.
    """
    user_msg = f"Now list the albums available on Spotify for '{query}'"
    info(f"Turn 2 — user: {user_msg!r}")
    history.append({"role": "user", "content": user_msg})

    try:
        reply = run_turn(client, agent_name, agent_version, history)
    except Exception as exc:
        fail(f"Agent call failed: {exc}")
        return False

    if not reply:
        fail("Agent returned an empty response for the albums query")
        return False

    info(f"Turn 2 — agent reply (first 600 chars):\n{reply[:600]}")

    keywords = ("album", "release", "discography", "record", "lp", "ep", "track", "single")
    reply_lower = reply.lower()
    if not any(kw in reply_lower for kw in keywords):
        fail("Response does not appear to contain album data")
        return False

    ok(f"Albums validated for query {query!r}")
    history.append({"role": "assistant", "content": reply})
    return True


def validate_query_tracks(
    client: AIProjectClient,
    agent_name: str,
    agent_version: str,
    query: str,
    history: list[dict],
) -> bool:
    """
    Turn 3 – ask the agent for the top tracks for the artist found in Turn 1.

    Appends the user message and assistant reply to *history*.
    Validates that the response contains track-related keywords.
    """
    user_msg = f"What are the top tracks on Spotify for '{query}'?"
    info(f"Turn 3 — user: {user_msg!r}")
    history.append({"role": "user", "content": user_msg})

    try:
        reply = run_turn(client, agent_name, agent_version, history)
    except Exception as exc:
        fail(f"Agent call failed: {exc}")
        return False

    if not reply:
        fail("Agent returned an empty response for the tracks query")
        return False

    info(f"Turn 3 — agent reply (first 600 chars):\n{reply[:600]}")

    keywords = ("track", "song", "title", "duration", "popularity", "play", "listen", "hit")
    reply_lower = reply.lower()
    if not any(kw in reply_lower for kw in keywords):
        fail("Response does not appear to contain track data")
        return False

    ok(f"Top tracks validated for query {query!r}")
    history.append({"role": "assistant", "content": reply})
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    query = sys.argv[1] if len(sys.argv) > 1 else "Radiohead"

    print(f"\n{'=' * 60}")
    print(f"  validate-spotify  —  query: {query}")
    print(f"{'=' * 60}\n")

    # Step 1: environment
    if not check_env():
        return 1

    # Step 2: project client
    info("Initialising Azure AI Project client...")
    try:
        client = create_project_client()
        ok("AIProjectClient initialised")
    except Exception as exc:
        fail(f"Failed to create AIProjectClient: {exc}")
        return 1

    # Step 4: create agent
    agent_name, agent_version = validate_create_agent(client)
    if agent_name is None:
        return 1

    # Shared conversation history
    history: list[dict] = []

    # Step 5: search query turn
    if not validate_search_query(client, agent_name, agent_version, query, history):
        return 1

    # Step 6: albums turn
    if not validate_query_albums(client, agent_name, agent_version, query, history):
        return 1

    # Step 7: top tracks turn
    if not validate_query_tracks(client, agent_name, agent_version, query, history):
        return 1

    print(f"\n{'=' * 60}")
    ok("All validations passed")
    print(f"{'=' * 60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
