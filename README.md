# agent-concert

**agent-concert** is a conversational AI agent specialized in concerts and live music. It lets you search for artists, explore past setlists, and discover touring history — powered by the [setlist.fm](https://www.setlist.fm/) database.

The agent is built with Azure AI Foundry (GPT-4.1) and accesses setlist.fm through an MCP (Model Context Protocol) server exposed via Azure API Management.

## Architecture

| Component | Technology |
|---|---|
| AI Platform | Azure AI Foundry (`azure-ai-projects`) |
| Model | GPT-4.1 Azure AI Foundry |
| Data source | setlist.fm API via Azure APIM (MCP server) |
| Web UI | Chainlit (port 8080) |
| HTTP API | aiohttp (port 8088) |
| Auth | Azure `DefaultAzureCredential` / Managed Identity |
| Package manager | [uv](https://github.com/astral-sh/uv) |

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Azure CLI — `az login` for local authentication
- An Azure deployment with AI Foundry + APIM (see [Deployment](#deployment-to-azure))

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Configure environment
cp .env.template .env
# Fill in .env with values from: azd env get-values

# 3. Authenticate with Azure
az login

# 4a. Run the Chainlit web UI (recommended)
uv run chainlit run src/app_chainlit.py --port 8080
# Open http://localhost:8080 in your browser

# 4b. Or run the HTTP API server
uv run src/agent.py
# Test: curl -X POST http://localhost:8088/responses \
#   -H "Content-Type: application/json" \
#   -d '{"input": "Tell me about Radiohead setlists"}'
```

## Running Locally

### Web UI (Chainlit)

The recommended way to interact with the agent locally is via the Chainlit web interface:

```bash
uv run chainlit run src/app_chainlit.py --port 8080
```

Open [http://localhost:8080](http://localhost:8080). The UI:
- Maintains **conversation history** across turns (you can ask follow-up questions without repeating context)
- Shows **MCP tool calls** (setlist.fm API lookups) as expandable steps

### HTTP API (aiohttp)

The agent also exposes a stateless REST API on port 8088:

```bash
uv run src/agent.py
```

Endpoints:

| Method | Path | Description |
|---|---|---|
| `POST` | `/responses` | Send a message. Body: `{"input": "..."}` |
| `GET` | `/health` | Health check. Returns `{"status": "healthy"}` |

Example:
```bash
curl -X POST http://localhost:8088/responses \
  -H "Content-Type: application/json" \
  -d '{"input": "What songs did Iron Maiden play in Paris in 2023?"}'
```

### VS Code Tasks

Convenience tasks are available via **Terminal → Run Task**:

| Task | Description |
|---|---|
| Install Dependencies | `uv sync` |
| Run Agent | HTTP API on port 8088 |
| Run Chainlit UI | Web UI on port 8080 |
| Test Agent (curl) | Quick curl test against the API |

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
│   ├── agent.py              # Core agent logic + aiohttp HTTP API (port 8088)
│   └── app_chainlit.py       # Chainlit web UI (port 8080)
├── infra/                    # Bicep infrastructure (Azure AI Foundry + APIM)
├── .chainlit/
│   └── config.toml           # Chainlit UI configuration
├── Dockerfile                # Container definition
├── pyproject.toml            # Python dependencies
├── azure.yaml                # AZD project configuration
└── .env.template             # Environment variable template
```

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `AZURE_AI_PROJECT_ENDPOINT` | Azure AI Foundry project endpoint URL | Yes |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Name of the deployed GPT model | Yes |
| `AZURE_SETLISTFM_MCP_URL` | MCP server URL (setlist.fm via APIM) | Yes |
| `AZURE_SETLISTFM_SUBSCRIPTION_KEY` | APIM subscription key | Yes |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Application Insights telemetry | No |

All values can be retrieved after provisioning with:
```bash
azd env get-values
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Import errors | `uv sync` |
| Authentication errors | `az login` (local), check Managed Identity RBAC (Azure) |
| Port in use | `lsof -ti :8088 \| xargs kill -9` |
| Missing env vars | `azd env get-values` then update `.env` |

## Resources

- [Azure AI Foundry Agents](https://learn.microsoft.com/azure/ai-foundry/agents/)
- [setlist.fm API](https://api.setlist.fm/docs/1.0/index.html)
- [Chainlit Documentation](https://docs.chainlit.io/)
- [uv Package Manager](https://github.com/astral-sh/uv)