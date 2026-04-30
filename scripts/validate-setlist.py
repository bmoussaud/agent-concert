"""
Validate the setlist.fm agent end-to-end.

Creates a 'validate-setlist' agent against the Azure AI Foundry project,
then runs a two-turn conversation:
  1. Search for an artist
  2. Get the last 5 setlists of that artist

Usage:
    uv run scripts/validate-setlist.py [artist_name]

    artist_name defaults to "Radiohead" when not supplied.

Required environment variables (loaded from .env):
    AZURE_AI_PROJECT_ENDPOINT          - Azure AI Foundry project endpoint
    AZURE_AI_MODEL_DEPLOYMENT_NAME     - Model deployment name
    AZURE_SETLISTFM_MCP_URL            - MCP server URL exposed through APIM
    AZURE_SETLISTFM_SUBSCRIPTION_KEY   - APIM subscription key
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
# Output helpers (same palette used in the other validate-* scripts)
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


# ---------------------------------------------------------------------------
# Validation steps
# ---------------------------------------------------------------------------

def check_env() -> bool:
    """Validate that all required environment variables are present."""
    required = {
        "AZURE_AI_PROJECT_ENDPOINT": os.getenv("AZURE_AI_PROJECT_ENDPOINT"),
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
        "AZURE_SETLISTFM_MCP_URL": os.getenv("AZURE_SETLISTFM_MCP_URL"),
        "AZURE_SETLISTFM_SUBSCRIPTION_KEY": os.getenv("AZURE_SETLISTFM_SUBSCRIPTION_KEY"),
        "AZURE_SPOTIFY_MCP_URL": os.getenv("AZURE_SPOTIFY_MCP_URL"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        fail(f"Missing environment variables: {', '.join(missing)}")
        return False
    ok(f"Project endpoint:  {required['AZURE_AI_PROJECT_ENDPOINT']}")
    ok(f"Model deployment:  {required['AZURE_AI_MODEL_DEPLOYMENT_NAME']}")
    ok(f"MCP URL:           {required['AZURE_SETLISTFM_MCP_URL']}")
    sub_key = required["AZURE_SETLISTFM_SUBSCRIPTION_KEY"]
    ok(f"Subscription key:  {'*' * 8}{sub_key[-4:]}")
    ok(f"Spotify MCP URL:   {required['AZURE_SPOTIFY_MCP_URL']}")
    ok("Spotify auth:      spotify-mcp-connection (project connection)")
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
    Create the 'validate-setlist' agent in Azure AI Foundry.

    Returns:
        (agent_name, agent_version) tuple.
    """
    instructions = (
        "You are a concert research assistant. "
        "You have access to the setlist.fm API through Azure API Management, which allows you to "
        "search for artists and retrieve their concert setlists. "
        "When asked to search for an artist, use the searchForArtists tool. "
        "When asked for setlists, use the searchForSetlists tool and return the results clearly, "
        "including the event date, venue name, city, and songs performed."
    )

    mcp_tool = MCPTool(
        server_label="agent-mcp-setlistfm",
        server_url=os.getenv("AZURE_SETLISTFM_MCP_URL"),
        require_approval="never",
        headers={
            "Ocp-Apim-Subscription-Key": str(os.getenv("AZURE_SETLISTFM_SUBSCRIPTION_KEY"))
        },
        project_connection_id="setlistfm-mcp-connection",
    )

    # Exclude 'searchForItem' tool: its 'type' parameter is an array type not supported
    # by Azure AI Foundry Agents MCP tool schema validation.
    spotify_mcp_tool = MCPTool(
        server_label="agent-mcp-spotify",
        server_url=os.getenv("AZURE_SPOTIFY_MCP_URL"),
        require_approval="never",
        allowed_tools=["searchForItem"],
        project_connection_id="spotify-mcp-connection",
    )

    with client.get_openai_client():
        agent = client.agents.create_version(
            agent_name="validate-setlist",
            definition=PromptAgentDefinition(
                model=os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME"),
                instructions=instructions,
                tools=[mcp_tool, spotify_mcp_tool],
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
        fail(f"Agent run did not complete successfully: response={response}")
        fail(f"Agent run ended with unexpected status: {response.status}")
        return None
    #print(f"Full agent response (debug): {response}")
    return response.output_text


def validate_create_agent(client: AIProjectClient) -> tuple[str, str] | tuple[None, None]:
    """Create the validate-setlist agent and report the result."""
    info("Creating 'validate-setlist' agent...")
    try:
        agent_name, agent_version = create_agent(client)
        ok(f"Agent created: name={agent_name!r}, version={agent_version!r}")
        return agent_name, agent_version
    except Exception as exc:
        fail(f"Failed to create agent: {exc}")
        return None, None


def validate_search_artist(
    client: AIProjectClient,
    agent_name: str,
    agent_version: str,
    artist: str,
    history: list[dict],
) -> bool:
    """
    Turn 1 – ask the agent to search for the given artist.

    Appends the user message and assistant reply to *history*.
    """
    user_msg = f"Search for the artist {artist}"
    info(f"Turn 1 — user: {user_msg!r}")
    history.append({"role": "user", "content": user_msg})

    try:
        reply = run_turn(client, agent_name, agent_version, history)
    except Exception as exc:
        fail(f"Agent call failed: {exc}")
        return False

    if not reply:
        fail("Agent returned an empty response for the artist search")
        return False

    info(f"Turn 1 — agent reply : {reply}")
    info(f"Turn 1 — ------")
    ok(f"Artist search completed for {artist!r}")
    # Append assistant reply so Turn 2 has the full context
    history.append({"role": "assistant", "content": reply})
    return True


def validate_get_setlists(
    client: AIProjectClient,
    agent_name: str,
    agent_version: str,
    history: list[dict],
) -> bool:
    """
    Turn 2 – ask the agent to retrieve the last 5 setlists of the previously found artist.

    Expects the reply to contain setlist/concert content.
    """
    user_msg = "Get the latest 5 setlists of this artist. If not found in the current year, get the latest 5 setlists available."
    info(f"Turn 2 — user: {user_msg!r}")
    history.append({"role": "user", "content": user_msg})

    try:
        reply = run_turn(client, agent_name, agent_version, history)
    except Exception as exc:
        fail(f"Agent call failed: {exc}")
        return False

    if not reply:
        fail("Agent returned an empty response for the setlists request")
        return False

    info(f"Turn 2 — agent reply:\n{reply}")
    info(f"Turn 2 — ------")

    # Basic content check: response should mention concert-related keywords
    keywords = ("setlist", "concert", "show", "venue", "date", "performed", "song", "track")
    reply_lower = reply.lower()
    if not any(kw in reply_lower for kw in keywords):
        fail("Response does not appear to contain setlist data")
        return False

    ok("Setlist data received and validated")
    # Append assistant reply so Turn 3 has the full context
    history.append({"role": "assistant", "content": reply})
    return True


def validate_average_setlist_with_spotify(
    client: AIProjectClient,
    agent_name: str,
    agent_version: str,
    artist: str,
    history: list[dict],
) -> bool:
    """
    Turn 3 – ask the agent to build an average setlist from the 5 latest shows
    and search each track on Spotify.

    Expects the reply to reference both setlist data and Spotify tracks.
    """
    user_msg = (
        f"I'm waiting for {artist}'s next concert! "
        "Using the 5 setlists we just retrieved, build an average setlist "
    )
    info(f"Turn 3 — user: {user_msg!r}")
    history.append({"role": "user", "content": user_msg})

    try:
        reply = run_turn(client, agent_name, agent_version, history)
    except Exception as exc:
        fail(f"Agent call failed: {exc}")
        return False

    if not reply:
        fail("Agent returned an empty response for the average setlist + Spotify request")
        return False

    info(f"Turn 3 — agent reply (first 800 chars):\n{reply[:800]}")

    # Validate that the response mentions both setlist and Spotify content
    reply_lower = reply.lower()
    setlist_keywords = ("setlist", "average", "most played", "frequently", "song", "track")
    spotify_keywords = ("spotify", "spotify.com", "open.spotify", "uri", "album", "artist")
    if not any(kw in reply_lower for kw in setlist_keywords):
        fail("Response does not appear to contain average setlist data")
        return False
    if not any(kw in reply_lower for kw in spotify_keywords):
        fail("Response does not appear to contain Spotify search results")
        return False

    ok("Average setlist built and Spotify tracks found")
    history.append({"role": "assistant", "content": reply})
    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    artist = sys.argv[1] if len(sys.argv) > 1 else "Radiohead"

    print(f"\n{'=' * 60}")
    print(f"  validate-setlist  —  artist: {artist}")
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

    # Step 3: create agent
    agent_name, agent_version = validate_create_agent(client)
    if agent_name is None:
        return 1

    # Shared conversation history — mutated across turns
    history: list[dict] = []

    # Step 4: Turn 1 — search for artist
    if not validate_search_artist(client, agent_name, agent_version, artist, history):
        return 1

    # Step 5: Turn 2 — get last 5 setlists
    if not validate_get_setlists(client, agent_name, agent_version, history):
        return 1

    # Step 6: Turn 3 — build average setlist and search each track on Spotify
    if not validate_average_setlist_with_spotify(client, agent_name, agent_version, artist, history):
        return 1

    print(f"\n{'=' * 60}")
    ok("All validations passed")
    print(f"{'=' * 60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
