# Automated Azure deployment and Foundry agent creation

The repository includes code for the entire Azure path:

```text
Azure Function -> remote MCP endpoint -> Foundry project connection
    -> prompt agent -> MCP tool call -> sample or real DB backend
```

The scripts create resources only when they are missing. Existing Function Apps are updated, the MCP connection is replaced with the current endpoint/key, and each agent run creates a new agent version. No cleanup or resource-deletion command runs automatically.

## 1. Required access and tools

You need:

- Permission to create resources in the selected subscription/resource group
- Permission to create or manage a Microsoft Foundry project, model deployment, project connection, and agent
- Azure CLI
- Azure Functions Core Tools v4
- Azure Developer CLI (`azd`)
- Python 3.13

Install all Microsoft Foundry extensions:

```powershell
azd ext install microsoft.foundry
```

Sign in. These commands can open the browser for MFA:

```powershell
az login
azd auth login
```

Check the prerequisites and authentication:

```powershell
.\scripts\Test-AzurePrerequisites.ps1
```

## 2. Install the repository dependencies

`requirements.txt` contains only Function App runtime packages. The separate Azure requirements file adds local deployment and Foundry SDK packages without sending them to the Function App.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-azure.txt
python -m pytest -q
```

## 3. Create the non-secret configuration

```powershell
Copy-Item azure\config.psd1.example azure\config.psd1
```

Edit `azure/config.psd1` and set:

- Subscription ID and region
- Resource group name
- Globally unique storage, Function App, and Foundry resource names
- Foundry project and agent names
- Model name, version, SKU, and capacity supported in the selected region

The default model values follow Microsoft's current `gpt-5-mini` CLI example. The provisioning script checks regional model availability before attempting deployment and stops with a useful command if the configured combination is unavailable.

`azure/config.psd1` is ignored by Git and excluded from Function deployment.

## 4. Set secrets for the current terminal

Use strong, different random values of at least 16 characters:

```powershell
$env:MCP_API_KEY="<strong-random-MCP-secret>"
$env:DB_API_KEY="<strong-random-DB-API-secret>"
```

The scripts store these values in Azure Function App Settings and the Foundry project connection. They are not written to the configuration file, source files, logs, or ZIP package.

## 5. Validate without changing Azure

```powershell
.\scripts\run_azure_pipeline.ps1 -ValidateOnly
```

This checks configuration keys, naming rules, HTTPS endpoints, and required secret presence. It does not contact Azure or create resources.

## 6. Run the complete pipeline

The following command creates billable Azure resources. Review the configuration first.

```powershell
.\scripts\run_azure_pipeline.ps1
```

It performs these operations in order:

1. Selects the configured Azure subscription.
2. Verifies that the region supports Flex Consumption.
3. Creates or reuses the resource group and storage account.
4. Creates or reuses a Python 3.13 Flex Consumption Function App.
5. securely configures both API keys and the backend switch.
6. Publishes the Python Function with an Azure remote build.
7. Waits for `/health` and runs MCP `initialize`, `tools/list`, and `tools/call` against Azure.
8. Creates or reuses the Foundry resource and project.
9. Creates or reuses the configured model deployment.
10. Creates the Foundry remote-tool connection with `X-API-Key`.
11. Creates a prompt-agent version with exactly four allowed MCP tools.
12. Sends an agent prompt that must generate an `mcp_call` trace and return Aarav Sharma.

Completion therefore proves the whole path, not just a successful deployment.

## Backend choices

For a self-contained Azure demonstration, keep:

```powershell
UseApi = $false
```

The MCP tools query the temporary sample SQLite database directly. The sample REST API remains protected by `DB_API_KEY`. Azure temporary storage is not persistent production storage.

For a separate production DB API, configure:

```powershell
UseApi       = $true
DbApiBaseUrl = "https://your-db-api.example.com"
```

The MCP tools then use `APIBackend` and send `DB_API_KEY` as `X-API-Key` to the configured API. The agent and MCP tool schemas remain unchanged.

## Individual operations

You can run each stage separately when troubleshooting:

```powershell
.\scripts\deploy_function.ps1 <parameters>
.\scripts\provision_foundry.ps1 <parameters>
.\scripts\configure_foundry.ps1 <parameters>
```

Run each command with `-?` to see its parameters. Use `-ValidateOnly` to validate that stage without Azure changes.

## Official references

- [Create and manage Flex Consumption Function Apps](https://learn.microsoft.com/en-us/azure/azure-functions/flex-consumption-how-to)
- [Python remote builds for Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/python-build-options)
- [Set up Microsoft Foundry resources and model deployments](https://learn.microsoft.com/en-us/azure/foundry/tutorials/quickstart-create-foundry-resources)
- [Connect Foundry agents to MCP endpoints](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/model-context-protocol)
- [Install the Foundry Azure Developer CLI extensions](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/install-cli-foundry-extensions)

