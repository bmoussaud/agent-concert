"""
agent-concert: Azure AI Foundry Agent for Concert Information

This agent uses Azure AI Projects and Agents API to provide concert-related 
information using the setlist.fm API via APIM.
"""
import asyncio
import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import MCPTool, PromptAgentDefinition
from aiohttp import web
import logging

# Load environment variables - override=False ensures Foundry runtime vars take precedence
load_dotenv(override=False)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)


def get_or_create_agent(project_client: AIProjectClient, model_deployment: str, setlistfm_mcp_url: str) -> dict:
    """
    Get existing agent or create a new one.
    
    Args:
        project_client: AIProjectClient instance
        model_deployment: Model deployment name
        setlistfm_mcp_url: URL of the setlist.fm MCP server exposed through API Management
        
    Returns:
        dict: A dictionary containing the agent's name and version
    """
    # Define agent instructions
    instructions = """
You are agent-concert, an AI assistant specialized in providing information about concerts and musical performances.

You have access to the setlist.fm API through Azure API Management, which allows you to:

    Returns:
        dict: A dictionary containing the agent's name and version
    """
    # Define agent instructions
    instructions = """
You are agent-concert, an AI assistant specialized in providing information about concerts and musical performances.

You have access to the setlist.fm API through Azure API Management, which allows you to:
- Search for artists and bands
- Find concert setlists and performance details
- Provide information about past and upcoming shows

You have access to the spotify API through Azure API Management, which allows you to:
- Search for artists and bands
- Retrieve artist information and biographies
- Get details about albums and tracks
- Manage user playlists and preferences

Your purpose is to help users discover concert information, find setlists from specific performances,
and learn about artists' touring history. Always be friendly, informative, and music-enthusiastic in your responses.

When users ask about concerts or artists, use your tools to search the setlist.fm database and provide
accurate, up-to-date information.
"""
    mcp_tool = MCPTool(
        server_label="agent-mcp-setlistfm",
        server_url=setlistfm_mcp_url,
        require_approval="never",
        headers={
            "Ocp-Apim-Subscription-Key": str(os.getenv("AZURE_SETLISTFM_SUBSCRIPTION_KEY"))
        },
        project_connection_id="setlistfm-mcp-connection"
    )

    # Exclude 'search' tool: its 'type' parameter is an array type, which is not
    # supported by Azure AI Foundry Agents MCP tool schema validation.
    # See: https://learn.microsoft.com/azure/ai-foundry/agents/how-to/tools/model-context-protocol#common-questions-and-errors
    spotify_mcp_tool = MCPTool(
        server_label="agent-mcp-spotify",
        server_url=os.getenv("AZURE_APIM_GATEWAY_URL") + "/spotify-mcp/mcp",
        require_approval="never",
        project_connection_id="spotify-mcp-connection",
        #allowed_tools=["getAnArtist", "getAnArtistsTopTracks", "getAnArtistsAlbums", "getAnAlbum", "getTrack", "getCurrentUsersProfile", "getCurrentUsersPlaylists"],
    )

    logger.info("Creating agent with the following configuration:")
    logger.info(f"Model deployment: {model_deployment}")
    logger.info(f"Using MCP tool with server URL: {setlistfm_mcp_url}")
    logger.info(f"MCP tool headers: {mcp_tool.headers}")

    with project_client.get_openai_client() as openai_client:
        agent = project_client.agents.create_version(
            agent_name="agent-concert",
            definition=PromptAgentDefinition(
                model=model_deployment,
                instructions=instructions,
                tools=[mcp_tool, spotify_mcp_tool],
            ),
        )
        logger.info(f"Created agent with ID: {agent.id}")
        return {'agent_name': agent.name, 'agent_version': agent.version}
   
    
def run_agent_conversation(project_client: AIProjectClient, agent_name: str, agent_version: str, history: list[dict]):
    """
    Run a conversation with the agent.

    Args:
        project_client: AIProjectClient instance
        agent_name: Agent name
        agent_version: Agent version
        history: Full conversation history as a list of {"role": ..., "content": ...} dicts

    Returns:
        Response object from the OpenAI Responses API (contains output_text and output items)
    """

    with project_client.get_openai_client() as openai_client:
        response = openai_client.responses.create(
            input=history,
            extra_body={"agent_reference": {"name": agent_name, "version": agent_version, "type": "agent_reference"}},
        )
        logger.info(f"Agent response received: {response}")
        logger.info(f"Run completed with status: {response.status}")
        return response


def project_client(project_endpoint: str) -> AIProjectClient:
    """
    Initialize the Azure AI Project Client and Agents Client.
    
    Returns:
        tuple: AIProjectClient
    """
    # Get configuration from environment
    project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    if not project_endpoint:
        raise ValueError("AZURE_AI_PROJECT_ENDPOINT environment variable is required")
    logger.info(f"Project endpoint: {project_endpoint}")
    
    # Create credential using DefaultAzureCredential for Azure authentication
    credential = DefaultAzureCredential()
    
    # Create project client - use endpoint directly
    project_client = AIProjectClient(
        credential=credential,
        endpoint=project_endpoint
    )
    
    logger.info("AIProjectClient Clients initialized successfully")
    return project_client


async def main():
    """
    Main entry point for the agent application.
    Creates the clients and starts HTTP server.
    """
    try:
        # Initialize clients
        model_deployment = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        if model_deployment is None:
            raise ValueError("AZURE_AI_MODEL_DEPLOYMENT_NAME environment variable is required")

        setlistfm_mcp_url = os.getenv("AZURE_SETLISTFM_MCP_URL")
        if setlistfm_mcp_url is None:
            raise ValueError("AZURE_SETLISTFM_MCP_URL environment variable is required")
        
        if not os.getenv("AZURE_AI_PROJECT_ENDPOINT"):
            raise ValueError("AZURE_AI_PROJECT_ENDPOINT environment variable is required")
        
        client = project_client(project_endpoint=os.getenv("AZURE_AI_PROJECT_ENDPOINT"))
        
        # Create or get agent
        agent_info = get_or_create_agent(client, model_deployment, setlistfm_mcp_url)
        agent_name = agent_info['agent_name']
        agent_version = agent_info['agent_version']

        if os.getenv("SMOKE_TEST") is not None:
            logger.info("Running smoke test...")
            user_message = "Can you provide details about recent concerts and setlists in 2026 performed by the band Eiffel?"
            logger.info(f"User message: {user_message}")
            test_response = run_agent_conversation(project_client=client, agent_name=agent_name, agent_version=agent_version, history=[{"role": "user", "content": user_message}])
            logger.info(f"Test {test_response.output_text}")


        if os.getenv("SMOKE_SPOTIFY") is not None:
            logger.info("Running smoke spotify test...")
            user_message = "Give me the information about the artist Radiohead and their top tracks."
            logger.info(f"User message: {user_message}")
            test_response = run_agent_conversation(project_client=client, agent_name=agent_name, agent_version=agent_version, history=[{"role": "user", "content": user_message}])
            logger.info(f"Test {test_response.output_text}")  

        # Create HTTP routes
        app = web.Application()
        
        # Store clients and agent ID in app context
        app['agent_name'] = agent_name
        app['agent_version'] = agent_version
        
        
        # Define HTTP handler for /responses endpoint
        async def handle_responses(request):
            """Handle POST requests to /responses endpoint."""
            try:
                data = await request.json()
                user_input = data.get('input', '')
                
                if not user_input:
                    return web.json_response({
                        'error': 'Missing input field'
                    }, status=400)
                
                logger.info(f"Received request: {user_input}")
                
                # Run agent conversation (stateless: single-turn history)
                response = run_agent_conversation(client,
                    agent_name=app['agent_name'],
                    agent_version=app['agent_version'],
                    history=[{"role": "user", "content": user_input}]
                )
                response_text = response.output_text
                
                # Return response in OpenAI Responses API format
                return web.json_response({
                    'id': 'response',
                    'object': 'response',
                    'content': response_text,
                    'status': 'completed'
                })
                
            except Exception as e:
                logger.error(f"Error processing request: {e}", exc_info=True)
                return web.json_response({
                    'error': str(e)
                }, status=500)
        
        # Add routes
        app.router.add_post('/responses', handle_responses)
        
        # Health check endpoint
        async def health_check(request):
            return web.json_response({'status': 'healthy'})
        
        app.router.add_get('/health', health_check)
        app.router.add_get('/', health_check)
        
        # Start server on port 8088
        port = int(os.getenv("PORT", "8088"))
        
        logger.info(f"Starting agent HTTP server on port {port}")
        runner = web.AppRunner(app)
        await runner.setup()
        
        try:
            # Configure site with SO_REUSEADDR to allow port reuse
            site = web.TCPSite(runner, '0.0.0.0', port, reuse_address=True)
            await site.start()
        except OSError as e:
            if e.errno == 98:  # Address already in use
                logger.error(f"Port {port} is already in use.")
                logger.error(f"To kill existing process manually: lsof -ti :{port} | xargs kill -9")
                logger.error(f"Or set AUTO_KILL_PORT=false to disable automatic cleanup.")
            raise
        
        logger.info(f"Agent HTTP server started successfully on port {port}")
        logger.info("- POST /responses - Send requests to the agent")
        logger.info("- GET /health - Health check endpoint")
        
        # Keep server running
        while True:
            await asyncio.sleep(3600)
        
    except Exception as e:
        logger.error(f"Failed to start agent: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())

