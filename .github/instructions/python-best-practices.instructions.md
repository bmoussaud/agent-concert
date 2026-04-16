---
applyTo: '**/*.py'
description: "Python coding standards for Azure AI Foundry applications. Use when writing, reviewing, or refactoring Python code. Covers type hints, async patterns, Azure SDK usage, dependency management with uv, testing, and security."
---

# Python Best Practices for Azure AI Foundry

## Language Features

- **Python 3.10+ only** — use modern syntax (match/case, union types `X | Y`, structural pattern matching)
- **Type hints everywhere** — functions, variables, class attributes; use modern generics (`list[str]`, `dict[str, Any]`, NOT `List`, `Dict` from `typing`)
- Use `from __future__ import annotations` for forward references when needed
- Prefer `pathlib.Path` over string paths

```python
from pathlib import Path
from typing import AsyncIterator

async def read_prompts(directory: Path) -> AsyncIterator[str]:
    """Load prompt files from directory."""
    for file in directory.glob("*.txt"):
        yield file.read_text(encoding="utf-8")
```

## Dependency Management

- **Use `uv` exclusively** for dependency management:
  - Add dependencies: `uv add <package>`
  - Run scripts: `uv run python script.py`
  - Sync environment: `uv sync`
- **Never use `pip install` directly** in this project
- Pin exact versions for production dependencies in `pyproject.toml`

## Azure SDK Patterns

### Authentication

Always use `DefaultAzureCredential` — works locally and in production:

```python
from azure.identity.aio import DefaultAzureCredential
from azure.ai.projects.aio import AIProjectClient

async with DefaultAzureCredential() as credential:
    async with AIProjectClient(
        endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        credential=credential
    ) as client:
        # Use client
        pass
```

### Async Operations

- **Prefer async** for all I/O operations (Azure SDK, file I/O, HTTP)
- Use async context managers (`async with`)
- Use `asyncio.gather()` for concurrent operations

```python
import asyncio
from azure.ai.inference.aio import ChatCompletionsClient

async def batch_inference(prompts: list[str]) -> list[str]:
    """Process multiple prompts concurrently."""
    async with ChatCompletionsClient(...) as client:
        tasks = [client.complete(prompt) for prompt in prompts]
        results = await asyncio.gather(*tasks)
        return [r.choices[0].message.content for r in results]
```

### Resource Cleanup

Always use context managers or explicit cleanup:

```python
# Good: Automatic cleanup
async with AIProjectClient(...) as client:
    result = await client.inference.get_chat_completions(...)

# Avoid: Manual cleanup required
client = AIProjectClient(...)
try:
    result = await client.inference.get_chat_completions(...)
finally:
    await client.close()
```

## Configuration & Secrets

- **Load from environment variables** — never hardcode
- Use `os.environ.get()` with defaults for optional settings
- Fail fast with `os.environ[KEY]` for required settings
- Validate configuration at startup

```python
import os
from dataclasses import dataclass

@dataclass
class Config:
    """Application configuration from environment."""
    ai_endpoint: str
    project_endpoint: str
    model_deployment: str
    app_insights_connection_string: str | None = None
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load and validate configuration from environment."""
        return cls(
            ai_endpoint=os.environ["AZURE_AI_FOUNDRY_ENDPOINT"],
            project_endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
            model_deployment=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
            app_insights_connection_string=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"),
        )
```

## Error Handling

- **Be specific** — catch specific exceptions, not bare `except:`
- **Log errors** with context before re-raising or converting
- **Use Azure SDK error types** — `AzureError`, `HttpResponseError`, `ResourceNotFoundError`
- **Exception chaining**: `raise NewException(...) from exc`
- **Fail-fast on startup** for missing configuration (raise `RuntimeError`)

```python
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
import logging

logger = logging.getLogger(__name__)

async def get_model_info(client: AIProjectClient, deployment_name: str) -> dict:
    """Retrieve model deployment information."""
    try:
        return await client.models.get(deployment_name)
    except ResourceNotFoundError:
        logger.error(f"Model deployment '{deployment_name}' not found")
        raise
    except HttpResponseError as e:
        logger.error(f"Azure API error: {e.status_code} - {e.message}")
        raise
```

## Type Hints

- Use **modern generic syntax**: `list[str]`, `dict[str, Any]`, `tuple[str, str]` (NOT `List`, `Dict`, `Tuple` from `typing`)
- All functions must have return type hints: `-> str`, `-> None`, `-> dict[str, Any]`
- Use `X | None` for nullable types (Python 3.10+)

## Code Style

- **Formatter**: Black (line-length = 100)
- **Import sorter**: isort with `profile = "black"`, `line_length = 100`
- **Linter**: flake8
- **Docstrings** for all public functions, classes, and modules (Google style)
- **Maximum line length**: 100 characters (not the default 79)
- **Imports order**: stdlib → third-party → local (use `isort`)
- Use 4-space indentation

```python
"""Module for Azure AI Foundry model interactions.

This module provides high-level interfaces for chat completions,
embeddings, and prompt management using Azure AI Foundry SDK.
"""

import asyncio
import os
from pathlib import Path
from typing import AsyncIterator

from azure.ai.inference.aio import ChatCompletionsClient
from azure.identity.aio import DefaultAzureCredential

from .config import Config
from .telemetry import track_inference
```

## Testing

- **Use pytest** with async support (`pytest-asyncio`)
- **Mock Azure SDK calls** — use `pytest-mock` or `unittest.mock`
- **Test files**: `tests/test_<module>.py`
- **Fixtures**: Share common setup in `tests/conftest.py`

```python
# tests/test_inference.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_chat_completion(mocker):
    """Test chat completion with mocked Azure client."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Test response"
    mock_client.complete.return_value = mock_response
    
    # Test your code with mock_client
    result = await your_function(mock_client, "test prompt")
    assert result == "Test response"
    mock_client.complete.assert_called_once()
```

## Security

- **Sanitize model outputs** before using in downstream operations
- **Validate input sizes** to prevent excessive API calls or memory usage
- **Rate limit** external requests where appropriate
- **Never log secrets** — redact credentials in logs

```python
def sanitize_model_output(output: str, max_length: int = 10000) -> str:
    """Sanitize and validate model output."""
    # Remove potential injection attempts
    sanitized = output.strip()
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized
```

## Logging

- Initialize at module level: `logger = logging.getLogger(__name__)`
- Suppress noisy Azure SDK loggers:

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)
```

## Observability

- **Log to Application Insights** for production
- **Use structured logging** with context
- **Track custom metrics** for model calls (tokens, latency, errors)

```python
import logging
from opencensus.ext.azure.log_exporter import AzureLogHandler

logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(
    connection_string=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
))

async def track_completion(prompt: str, response: str, duration_ms: float):
    """Log completion with telemetry."""
    logger.info(
        "Chat completion",
        extra={
            "custom_dimensions": {
                "prompt_length": len(prompt),
                "response_length": len(response),
                "duration_ms": duration_ms,
            }
        }
    )
```

## Common Patterns

### Loading Prompts

```python
from pathlib import Path

def load_prompt(name: str) -> str:
    """Load prompt template from file."""
    prompt_dir = Path(__file__).parent / "prompts"
    prompt_file = prompt_dir / f"{name}.txt"
    
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt not found: {name}")
    
    return prompt_file.read_text(encoding="utf-8")
```

### Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential
from azure.core.exceptions import HttpResponseError

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True
)
async def call_with_retry(client: ChatCompletionsClient, prompt: str) -> str:
    """Call Azure API with exponential backoff retry."""
    response = await client.complete(prompt)
    return response.choices[0].message.content
```

## Anti-Patterns to Avoid

❌ Synchronous Azure SDK calls — use async variants  
❌ Hardcoded credentials or endpoints  
❌ Bare `except:` clauses  
❌ Using `pip` instead of `uv`  
❌ Missing type hints  
❌ Not using context managers for Azure clients  
❌ Logging secrets or sensitive data  
❌ Ignoring Azure SDK errors
