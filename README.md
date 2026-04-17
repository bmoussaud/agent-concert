# agent-concert

An Azure AI Foundry agent that provides concert information using the setlist.fm API through Azure API Management.

## Overview

This agent uses the Microsoft Agent Framework with Azure AI Foundry to help users discover:
- Concert setlists and performance details
- Artist and band information
- Touring history and upcoming shows

## Architecture

- **SDK**: Azure AI Projects (`azure-ai-projects`) — `AIProjectClient` + `PromptAgentDefinition`
- **AI Platform**: Azure AI Foundry
- **Model**: GPT-4.1-mini (deployed via Azure AI Foundry)
- **HTTP Server**: aiohttp server (port 8088)
- **API Gateway**: Azure API Management (for setlist.fm API)
- **Package Manager**: uv (fast Python dependency management)
- **Authentication**: Azure DefaultAzureCredential (Managed Identity in production)

## Prerequisites

- [uv](https://github.com/astral-sh/uv) (Python package manager)
- Python 3.10 or higher
- Azure CLI (`az login` for local development)
- Azure AI Foundry project with deployed model
- Azure API Management with setlist.fm API configured

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python dependency management.

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Install dependencies from pyproject.toml**:
   ```bash
   uv sync
   ```

3. **Configure environment variables**:
   ```bash
   cp .env.template .env
   # Edit .env and fill in your Azure AI Foundry configuration
   ```

4. **Get values from your Azure deployment**:
   ```bash
   azd env get-values
   # Copy AZURE_AI_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME to .env
   ```

## Running Locally

1. **Authenticate with Azure**:
   ```bash
   az login
   ```

2. **Start the agent**:
   ```bash
   uv run src/agent.py
   ```

3. **Test the agent**:
   The agent runs as an HTTP service on `http://localhost:8088`. Send a test request:
   ```bash
   curl -X POST http://localhost:8088/responses \
     -H "Content-Type: application/json" \
     -d '{"input": "Tell me about concert setlists"}'
   ```

## Deployment to Azure

### Option 1: Deploy with Azure Developer CLI (azd)

If you have `azd` configured, you can deploy the infrastructure and agent:

```bash
# Provision Azure resources
azd provision

# Deploy the agent
azd deploy
```

### Option 2: Manual Docker Deployment

Build and deploy the containerized agent manually:

```bash
# Build the Docker image (MUST use linux/amd64 platform)
docker build --platform linux/amd64 -t agent-concert:latest .

# Tag for your Azure Container Registry
docker tag agent-concert:latest <your-acr>.azurecr.io/agent-concert:latest

# Push to ACR
az acr login --name <your-acr>
docker push <your-acr>.azurecr.io/agent-concert:latest

# Deploy to Azure AI Foundry using the microsoft-foundry skill or Azure portal
```

## Project Structure

```
agent-concert/
├── src/
│   └── agent.py              # Main agent implementation
├── infra/                    # Bicep infrastructure code
├── agent.yaml                # Agent deployment configuration
├── Dockerfile                # Container definition
├── pyproject.toml            # Python dependencies and project config
├── .env.template             # Environment variable template
└── README.md                 # This file
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_AI_PROJECT_ENDPOINT` | Azure AI Foundry project endpoint URL | Yes |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Name of the deployed GPT model | Yes |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Application Insights for telemetry | No |

## Development Notes

### Dependency Management with uv

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python package management. Benefits:

- **10-100x faster** than pip for dependency resolution and installation
- **Reliable** dependency resolution with proper conflict detection
- **Compatible** with pip and existing tools

All dependencies are declared in `pyproject.toml` and installed with `uv sync`.

**Note**: We use a simplified dependency set without `azure-ai-agentserver-*` packages, which had version conflicts. Instead, we implement a custom HTTP server using `aiohttp`.

### Dependencies

All dependencies are declared in `pyproject.toml` and installed with `uv sync`:

```toml
[project]
requires-python = ">=3.10"
dependencies = [
    # Azure AI Projects and Agents
    "azure-ai-projects>=2.0.0",
    # HTTP server
    "aiohttp>=3.9.0",
    # Configuration management
    "python-dotenv>=1.0.1",
]

[tool.uv.pip]
prerelease = "allow"
```

### Authentication

- **Local development**: Uses `DefaultAzureCredential` which picks up credentials from `az login`
- **Production**: Uses Managed Identity automatically when deployed to Azure

### How the Agent Works

On startup, the agent:

1. Creates an `AIProjectClient` using `DefaultAzureCredential` and the configured project endpoint.
2. Registers a versioned agent definition via `project_client.agents.create_version()` using `PromptAgentDefinition` (model + instructions).
3. Starts the aiohttp HTTP server on port 8088.

For each incoming request, the handler calls `openai_client.responses.create()` with an `agent_reference` pointing to the registered agent name and version, then returns the response text.

### HTTP Server

The agent implements a custom HTTP server using `aiohttp` that exposes an API compatible with the Foundry Responses format:

- **POST /responses** - Send requests to the agent
  - Request: `{"input": "your message here"}`
  - Response: `{"id": "response", "object": "response", "content": "...", "status": "completed"}`
- **GET /health** - Health check endpoint (returns `{"status": "healthy"}`)
- **GET /** - Root endpoint (also returns health status)

The server runs on `0.0.0.0:8088` by default, making it accessible from any network interface.

## Troubleshooting

### Import Errors
If you see import errors for `azure.ai.projects`, ensure dependencies are installed:
```bash
uv sync
```

### Missing aiohttp Module
If you see `ModuleNotFoundError: No module named 'aiohttp'`, this dependency is required for the HTTP server. Run:
```bash
uv sync
```

### Authentication Errors
- **Locally**: Run `az login` first
- **In Azure**: Ensure the managed identity has proper RBAC roles on the AI Foundry project

### Connection Errors
Verify the `AZURE_AI_PROJECT_ENDPOINT` environment variable is set correctly in your `.env` file.

### Port Already in Use
If port 8088 is already in use, stop the existing process:
```bash
# Find the process using port 8088
lsof -i :8088
# Kill the process (replace PID with actual process ID)
kill -9 <PID>
```

## Resources

- [Microsoft Agent Framework Documentation](https://learn.microsoft.com/azure/ai-foundry/agents/)
- [Azure AI Foundry](https://learn.microsoft.com/azure/ai-foundry/)
- [Hosted Agents Concepts](https://learn.microsoft.com/azure/ai-foundry/agents/concepts/hosted-agents)
- [uv Package Manager](https://github.com/astral-sh/uv)
- [aiohttp Documentation](https://docs.aiohttp.org/)

## Quick Start Commands

```bash
# Install uv (first time only)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Configure environment
cp .env.template .env
# Edit .env with your Azure AI Foundry values

# Run locally
az login
uv run src/agent.py

# Test the agent
curl -X POST http://localhost:8088/responses \
  -H "Content-Type: application/json" \
  -d '{"input": "Tell me about Coldplay concerts"}'
```