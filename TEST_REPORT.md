# Verification report

Date: 2026-09-01

Environment:

- Windows
- Python 3.13.5
- MCP Python SDK 2.1.1
- Azure Functions Python library 2.3.0
- Azure AI Projects SDK 2.5.0

## Automated suite

Command:

```powershell
python -m pytest -q
```

Result:

```text
14 passed
```

Covered behavior:

- Environment configuration and `USE_API` parsing
- SQLite initialization, seeding, filtering, and missing records
- Order filtering and sales calculations
- Sample API routes and DB API-key rejection
- Direct SQLite and HTTP API backend selection
- MCP registry containing exactly four tools
- Direct registered tool execution and structured output
- MCP API-key rejection
- MCP `initialize`, `tools/list`, and `tools/call` over Streamable HTTP
- Foundry prompt-agent definition, MCP project connection reference, and four-tool allowlist
- Agent-level smoke-test enforcement of both an `mcp_call` trace and expected grounded data

## Live API-mode smoke test

The application was started on a real local TCP port with:

```text
USE_API=true
DB_API_BASE_URL=http://127.0.0.1:8765
DB_API_KEY=sample-db-key
MCP_API_KEY=sample-mcp-key
```

The smoke client successfully completed:

```text
initialize -> tools/list -> tools/call(get_customer, customer_id=1)
```

Observed tool registry:

```text
get_customer, search_customers, list_orders, get_sales_summary
```

Observed structured result:

```json
{
  "id": 1,
  "name": "Aarav Sharma",
  "email": "aarav.sharma@example.com",
  "country": "India",
  "tier": "Gold"
}
```

This live test exercised the complete sample path:

```text
MCP HTTP request -> MCP tool -> APIBackend -> sample DB API -> SQLite -> MCP response
```

## Azure Functions validation

- All Python sources compiled successfully.
- `function_app.py` imported successfully.
- Azure Functions indexed one `AsgiFunctionApp` named `digvijay_mcp` with two bindings.

Azure deployment and Microsoft Foundry execution require the user's Azure subscription, project, model deployment, and permissions, so those external checks are intentionally performed after transfer.

## Azure automation dry run

The full PowerShell pipeline was executed with `-ValidateOnly`. It successfully validated Function configuration, Foundry resource/model configuration, MCP endpoint wiring, agent configuration, names, URLs, and required secret presence without contacting or changing Azure.

All PowerShell deployment files passed the PowerShell parser, and `create_foundry_agent.py` compiled and loaded its command-line interface successfully against `azure-ai-projects==2.5.0`.
