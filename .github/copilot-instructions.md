# GitHub Copilot Instructions for content-understanding

## Project Overview

This project is an **Azure AI Content Understanding** application that leverages Azure AI Foundry to analyze and extract structured information from various content types (documents, images, audio, video). It is built with Python and deploys infrastructure to Azure using Bicep and the Azure Developer CLI (AZD).

## Tech Stack

- **Language**: Python 3 (managed with [uv](https://github.com/astral-sh/uv))
- **AI Platform**: Azure AI Foundry (AI project + model deployments)
- **Models**: OpenAI GPT-4.1-mini deployed via Azure AI Foundry
- **Infrastructure as Code**: Bicep (Azure Resource Manager)
- **Deployment Tool**: Azure Developer CLI (`azd`)
- **Observability**: Azure Application Insights + Log Analytics
- **Dev Environment**: VS Code Dev Containers (Python 3, Azure CLI, AZD, Docker, Node.js)

## Repository Structure

```
.
├── .devcontainer/       # Dev container configuration (Python 3 + tooling)
├── .github/             # GitHub Copilot instructions and CI/CD workflows
│   ├── instructions/    # Copilot instruction files for code conventions
│   └── skills/          # Copilot skills (conventional-commit, etc.)
├── infra/               # Bicep infrastructure code
│   ├── main.bicep       # Entry point for all Azure resources
│   ├── main.parameters.json
│   └── modules/         # Modular Bicep resource definitions
├── azure.yaml           # AZD project configuration
└── README.md
```

## Development Guidelines

### Python

- Use **Python 3.10+** features and type hints throughout
- Manage dependencies and virtual environments with **uv** (`uv add`, `uv run`, `uv sync`)
- Follow **PEP 8** style; use `autopep8` for formatting
- Prefer **async/await** patterns for I/O-bound operations (Azure SDK async clients)
- Use **Azure SDK for Python** (`azure-ai-*` packages) for AI Foundry integration
- Load configuration from **environment variables** (never hardcode secrets)
- Read Azure AI credentials from environment (see `azure.yaml` outputs):
  - `AZURE_AI_FOUNDRY_ENDPOINT`
  - `AZURE_AI_PROJECT_ENDPOINT`
  - `AZURE_AI_MODEL_DEPLOYMENT_NAME`
  - `APPLICATIONINSIGHTS_CONNECTION_STRING`

### Azure AI Foundry

- Prefer the **Azure AI Foundry SDK** (`azure-ai-projects`, `azure-ai-inference`) for model calls
- Use **managed identity** where possible; fall back to `DefaultAzureCredential` for local dev
- Log model calls with Application Insights for observability
- Keep prompts in dedicated files under `prompts/` and load them programmatically

### Infrastructure (Bicep)

- Follow Bicep best practices: lowerCamelCase names, `@description` decorators on all parameters
- Use `uniqueString()` with meaningful prefixes for resource naming
- **Never** include secrets in Bicep outputs
- Run `az bicep build --file infra/main.bicep` to validate after any Bicep change
- See `.github/instructions/bicep-code-best-practices.instructions.md` for detailed guidance
- See `.github/instructions/azure-verified-modules-bicep.instructions.md` for AVM guidance

### Security

- Never hardcode API keys, connection strings, or other secrets
- Use Azure Managed Identity and `DefaultAzureCredential` for authentication
- Follow OWASP guidelines — see `.github/instructions/security-and-owasp.instructions.md`
- Sanitize all model outputs before using in downstream operations

### CI/CD (GitHub Actions)

- Use OIDC for Azure authentication (avoid long-lived credentials)
- Pin action versions to full commit SHAs or specific version tags
- Grant `GITHUB_TOKEN` least-privilege permissions
- See `.github/instructions/github-actions-ci-cd-best-practices.instructions.md` for detailed guidance

### Git Commit Messages

- Follow **Conventional Commits** specification: `<type>[scope]: <description>`
- Use imperative mood: "add feature" not "added feature"
- Keep subject line under 72 characters
- Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`
- See `.github/instructions/git-commit-messages.instructions.md` for detailed guidance and examples

## AZD Workflow

```bash
# Provision Azure resources
azd provision

# Deploy application
azd deploy

# Provision + deploy in one step
azd up

# Set up environment variables locally after provisioning
azd env get-values
```

## Key Conventions

1. **No secrets in code or outputs** — always use environment variables or Azure Key Vault
2. **Use `uv` for Python dependency management** — not pip directly
3. **Validate Bicep changes** with `az bicep build` before committing
4. **Use `DefaultAzureCredential`** for Azure authentication in Python code
5. **Write tests** using `pytest`; mock Azure SDK calls in unit tests
