# Architecture

## Current self-contained test

```text
MCP client or agent
        |
        | Streamable HTTP + X-API-Key
        v
     /mcp
        |
        v
Four registered MCP tools
        |
        | USE_API=false
        v
SQLiteBackend -> SQLite sample database
```

## API-contract test and future production flow

```text
MCP client or agent
        |
        v
     /mcp
        |
        v
Four registered MCP tools
        |
        | USE_API=true
        v
APIBackend -> Sample or real DB API -> Database
```

## Azure agent flow

```text
User prompt
    |
    v
Microsoft Foundry prompt agent
    |
    | MCP tool + Foundry project connection
    | X-API-Key injected by Foundry
    v
Azure Function /mcp
    |
    v
Allowed read-only tool -> selected backend -> data source
```

## Component responsibilities

| Component | Responsibility |
| --- | --- |
| `app/mcp_server.py` | Registers the four agent-visible MCP tools |
| `app/backends.py` | Selects direct SQLite or HTTP API behavior |
| `app/mock_api.py` | Implements the replaceable sample DB API contract |
| `app/database.py` | Creates, seeds, and queries the sample SQLite database |
| `app/asgi.py` | Combines REST, health, authentication, and MCP into one ASGI app |
| `function_app.py` | Exposes the ASGI application to Azure Functions |
| `scripts/smoke_test.py` | Verifies discovery and a tool call over real MCP HTTP messages |
| `scripts/deploy_function.ps1` | Provisions and deploys the Flex Consumption Function App |
| `scripts/provision_foundry.ps1` | Provisions the Foundry resource, project, and model deployment |
| `scripts/configure_foundry.ps1` | Creates the authenticated MCP connection and invokes agent creation |
| `scripts/create_foundry_agent.py` | Creates a versioned prompt agent and performs the agent-level MCP test |
| `scripts/run_azure_pipeline.ps1` | Runs the complete Azure sequence from one configuration file |

`USE_API` is only a backend switch. It does not create an API. The included sample API is the concrete API implementation used to test that switch.

All tool operations are read-only. Secrets are supplied through environment variables or Azure Function App Settings and are never committed to source control.
