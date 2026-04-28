"""
agent-concert: Chainlit Web UI

Provides a conversational web interface for the agent-concert agent.
Reuses core logic from agent.py and displays MCP tool calls as visible steps.

Run with:
    uv run chainlit run src/app_chainlit.py --port 8080
"""
import asyncio
import os
import logging

import chainlit as cl
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

from agent import get_or_create_agent, run_agent_conversation, project_client as make_project_client

# Load environment variables
load_dotenv(override=False)

logger = logging.getLogger(__name__)


@cl.on_chat_start
async def on_chat_start():
    """Initialize the Azure AI client and agent for this chat session."""
    project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    model_deployment = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    setlistfm_mcp_url = os.getenv("AZURE_SETLISTFM_MCP_URL")

    missing = [
        name for name, val in [
            ("AZURE_AI_PROJECT_ENDPOINT", project_endpoint),
            ("AZURE_AI_MODEL_DEPLOYMENT_NAME", model_deployment),
            ("AZURE_SETLISTFM_MCP_URL", setlistfm_mcp_url),
        ] if not val
    ]
    if missing:
        await cl.Message(
            content=f"⚠️ Missing environment variables: {', '.join(missing)}. "
                    "Please check your `.env` file."
        ).send()
        return

    try:
        client = make_project_client(project_endpoint=project_endpoint)
        agent_info = await asyncio.to_thread(
            get_or_create_agent, client, model_deployment, setlistfm_mcp_url
        )
        cl.user_session.set("client", client)
        cl.user_session.set("agent_name", agent_info["agent_name"])
        cl.user_session.set("agent_version", agent_info["agent_version"])
        cl.user_session.set("history", [])

        await cl.Message(
            content="👋 Hi! I'm **agent-concert**, your concert setlist assistant.\n\n"
                    "Ask me about artists, setlists, or past performances — "
                    "I'll search setlist.fm for you!"
        ).send()

    except Exception as exc:
        logger.exception("Failed to initialize agent")
        await cl.Message(content=f"❌ Failed to initialize agent: {exc}").send()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle an incoming user message and stream the agent response."""
    client: AIProjectClient | None = cl.user_session.get("client")
    agent_name: str | None = cl.user_session.get("agent_name")
    agent_version: str | None = cl.user_session.get("agent_version")

    if not client or not agent_name or not agent_version:
        await cl.Message(
            content="⚠️ Session not initialized. Please refresh the page."
        ).send()
        return

    # Accumulate conversation history
    history: list[dict] = cl.user_session.get("history") or []
    history.append({"role": "user", "content": message.content})

    # Call the (synchronous) agent in a thread to avoid blocking the event loop
    response = await asyncio.to_thread(
        run_agent_conversation,
        client,
        agent_name,
        agent_version,
        history,
    )

    # Display MCP tool calls as Chainlit steps
    consent_requested = False
    if hasattr(response, "output") and response.output:
        for item in response.output:
            item_type = getattr(item, "type", None)

            # Function/tool call step (MCP tool invocations)
            if item_type == "function_call":
                tool_name = getattr(item, "name", "tool")
                tool_args = getattr(item, "arguments", "")
                async with cl.Step(name=f"🔧 {tool_name}", type="tool") as step:
                    step.input = tool_args

            # Function call output (result returned by the MCP tool)
            elif item_type == "function_call_output":
                output_value = getattr(item, "output", "")
                # Attach result to the last open step if possible
                async with cl.Step(name="📦 Tool result", type="tool") as step:
                    step.output = output_value

            # OAuth consent required — display a clickable link to authorize
            elif item_type == "oauth_consent_request":
                consent_link = getattr(item, "consent_link", None)
                server_label = getattr(item, "server_label", "a service")
                if consent_link:
                    consent_requested = True
                    await cl.Message(
                        content=(
                            f"🔐 **Authorization required for {server_label}**\n\n"
                            f"Please [click here to authorize]({consent_link}) and then resend your message."
                        )
                    ).send()

    if consent_requested:
        # Don't append an empty assistant turn; wait for the user to re-send after consent
        return

    # Persist updated history (append assistant turn)
    history.append({"role": "assistant", "content": response.output_text})
    cl.user_session.set("history", history)

    # Send the final text response
    await cl.Message(content=response.output_text).send()
