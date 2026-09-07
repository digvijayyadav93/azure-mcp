[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$ProjectEndpoint,
    [Parameter(Mandatory)] [string]$ModelDeploymentName,
    [Parameter(Mandatory)] [string]$McpServerUrl,
    [Parameter(Mandatory)] [string]$ConnectionName,
    [string]$AgentName = "customer-data-agent",
    [string]$PythonExecutable = "python",
    [switch]$SkipAgentSmokeTest,
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-CommandSucceeded([string]$Description) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

foreach ($url in @($ProjectEndpoint, $McpServerUrl)) {
    if ($url -notmatch '^https://') {
        throw "Foundry and MCP endpoints must use HTTPS. Invalid value: $url"
    }
}
foreach ($name in @($ModelDeploymentName, $ConnectionName, $AgentName)) {
    if ($name -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,62}[a-zA-Z0-9]$') {
        throw "Model, connection, and agent names must contain 3-64 letters, numbers, dots, underscores, or hyphens. Invalid value: $name"
    }
}
if (-not $env:MCP_API_KEY -or $env:MCP_API_KEY.Length -lt 16) {
    throw "Set MCP_API_KEY to the same 16+ character value deployed to the Function App."
}

if ($ValidateOnly) {
    Write-Host "Foundry connection and agent configuration are valid. No Azure changes were made."
    return
}

$null = & azd auth login --check-status --no-prompt
Assert-CommandSucceeded "Checking Azure Developer CLI authentication"

$null = & azd ai project set $ProjectEndpoint --no-prompt
Assert-CommandSucceeded "Selecting the Foundry project"

$null = & azd ai project show --output json --no-prompt
Assert-CommandSucceeded "Verifying the Foundry project context"

Write-Host "Creating or replacing the authenticated MCP project connection..."
$null = & azd ai connection create $ConnectionName `
    --kind remote-tool `
    --target $McpServerUrl `
    --auth-type custom-keys `
    --custom-key "X-API-Key=$($env:MCP_API_KEY)" `
    --force `
    --no-prompt `
    --output json
Assert-CommandSucceeded "Creating the Foundry MCP connection"

$repoRoot = Split-Path -Parent $PSScriptRoot
$arguments = @(
    "scripts\create_foundry_agent.py",
    "--project-endpoint", $ProjectEndpoint,
    "--model", $ModelDeploymentName,
    "--mcp-server-url", $McpServerUrl,
    "--connection-name", $ConnectionName,
    "--agent-name", $AgentName
)
if ($SkipAgentSmokeTest) {
    $arguments += "--skip-smoke-test"
}

Push-Location $repoRoot
try {
    Write-Host "Creating a Foundry agent version and running the end-to-end check..."
    & $PythonExecutable @arguments
    Assert-CommandSucceeded "Creating and testing the Foundry agent"
}
finally {
    Pop-Location
}

Write-Host "Foundry connection and agent creation passed."

