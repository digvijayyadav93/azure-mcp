# Azure MCP Server

A complete sample showing how a Microsoft Foundry agent can call customer-data tools through a remote MCP server hosted in Azure Functions.

The same four MCP tools work with either backend:

- `USE_API=false`: MCP tools query the included SQLite sample database directly.
- `USE_API=true`: MCP tools call a sample or production DB API over HTTP.

This makes the sample API replaceable later without changing the agent or MCP tool definitions.

## Included components

- MCP Streamable HTTP endpoint at `/mcp`
- Four registered read-only tools: `get_customer`, `search_customers`, `list_orders`, and `get_sales_summary`
- Sample DB API under `/api`
- SQLite schema and deterministic sample data
- Separate SQLite and HTTP API backend adapters
- `X-API-Key` protection for MCP and DB API traffic
- Azure Functions Python v2 entry point
- Parameterized Azure Function and Microsoft Foundry provisioning scripts
- Foundry prompt-agent creation code with an authenticated MCP connection and tool allowlist
- Automated database, API, registry, authentication, and MCP protocol tests
- Standalone smoke-test script, so Postman and Node.js are not required

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the component flow and [docs/AZURE_DEPLOYMENT.md](docs/AZURE_DEPLOYMENT.md) for deployment and agent connection steps.

## Automated Azure plumbing

After signing into Azure, the included pipeline can create or reuse all required resources, deploy the MCP Function App, create the Foundry project and model deployment, register the MCP API-key connection, create the agent, and run the final agent test.

```powershell
python -m pip install -r requirements-azure.txt
Copy-Item azure\config.psd1.example azure\config.psd1
# Edit azure\config.psd1 with globally unique resource names.

$env:MCP_API_KEY="<strong-random-MCP-secret>"
$env:DB_API_KEY="<strong-random-DB-API-secret>"

.\scripts\run_azure_pipeline.ps1 -ValidateOnly
.\scripts\run_azure_pipeline.ps1
```

The actual run creates billable Azure resources. Review the configuration and validation output first. Secrets are never stored in the configuration file or repository.

## Quick start on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pytest -v
```

Start the server in direct SQLite mode:

```powershell
$env:MCP_API_KEY="temporary-test-key"
$env:USE_API="false"
python run.py
```

In a second PowerShell window, verify MCP discovery and a real tool call:

```powershell
python scripts\smoke_test.py --url http://127.0.0.1:8000/mcp --api-key temporary-test-key
```

Expected tool names:

```text
get_customer, search_customers, list_orders, get_sales_summary
```

## Full sample-API mode

This mode exercises the future production architecture locally:

```powershell
$env:USE_API="true"
$env:DB_API_BASE_URL="http://127.0.0.1:8000"
$env:DB_API_KEY="temporary-db-api-key"
$env:MCP_API_KEY="temporary-test-key"
python run.py
```

The request path is:

```text
MCP client -> /mcp -> APIBackend -> /api -> SQLite -> MCP response
```

## Sample API contract

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health |
| `GET` | `/api/customers/{id}` | Get one customer |
| `GET` | `/api/customers?name=&country=&tier=` | Search customers |
| `GET` | `/api/orders?customer_id=&status=` | List/filter orders |
| `GET` | `/api/customers/{id}/sales-summary` | Customer sales summary |

To use a real DB API later, implement these response shapes, set `USE_API=true`, and change `DB_API_BASE_URL` and `DB_API_KEY`. No MCP or agent changes are required.

## Sample records

- Customer 1: Aarav Sharma, India, Gold
- Customer 2: Emma Wilson, UK, Silver
- Customer 3: Kenji Sato, Japan, Gold
- Five orders across the three customers

The SQLite database is created and seeded automatically. It is sample data only and is not intended as persistent Azure storage.
