[CmdletBinding()]
param(
    [string]$ConfigPath = "azure\config.psd1",
    [string]$PythonExecutable = "python",
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$resolvedConfig = if ([System.IO.Path]::IsPathRooted($ConfigPath)) {
    $ConfigPath
} else {
    Join-Path $repoRoot $ConfigPath
}

if (-not (Test-Path -LiteralPath $resolvedConfig -PathType Leaf)) {
    throw "Configuration file not found: $resolvedConfig. Copy azure\config.psd1.example to azure\config.psd1 and fill in the values."
}

$config = Import-PowerShellDataFile -LiteralPath $resolvedConfig
$requiredKeys = @(
    "SubscriptionId", "Location", "ResourceGroupName", "StorageAccountName",
    "FunctionAppName", "PythonVersion", "UseApi", "DbApiBaseUrl",
    "FoundryResourceName", "FoundryProjectName", "ModelDeploymentName",
    "ModelName", "ModelVersion", "ModelFormat", "ModelSkuName",
    "ModelSkuCapacity", "AgentName", "McpConnectionName", "SkipAgentSmokeTest"
)
foreach ($key in $requiredKeys) {
    if (-not $config.ContainsKey($key)) {
        throw "Missing '$key' in $resolvedConfig."
    }
}

& (Join-Path $PSScriptRoot "Test-AzurePrerequisites.ps1") `
    -SkipLoginCheck:$ValidateOnly `
    -SkipToolCheck:$ValidateOnly

& (Join-Path $PSScriptRoot "deploy_function.ps1") `
    -SubscriptionId $config.SubscriptionId `
    -Location $config.Location `
    -ResourceGroupName $config.ResourceGroupName `
    -StorageAccountName $config.StorageAccountName `
    -FunctionAppName $config.FunctionAppName `
    -PythonVersion $config.PythonVersion `
    -UseApi $config.UseApi `
    -DbApiBaseUrl $config.DbApiBaseUrl `
    -PythonExecutable $PythonExecutable `
    -ValidateOnly:$ValidateOnly

$projectEndpoint = & (Join-Path $PSScriptRoot "provision_foundry.ps1") `
    -SubscriptionId $config.SubscriptionId `
    -Location $config.Location `
    -ResourceGroupName $config.ResourceGroupName `
    -FoundryResourceName $config.FoundryResourceName `
    -FoundryProjectName $config.FoundryProjectName `
    -ModelDeploymentName $config.ModelDeploymentName `
    -ModelName $config.ModelName `
    -ModelVersion $config.ModelVersion `
    -ModelFormat $config.ModelFormat `
    -ModelSkuName $config.ModelSkuName `
    -ModelSkuCapacity $config.ModelSkuCapacity `
    -ValidateOnly:$ValidateOnly

$mcpServerUrl = "https://$($config.FunctionAppName).azurewebsites.net/mcp"
& (Join-Path $PSScriptRoot "configure_foundry.ps1") `
    -ProjectEndpoint $projectEndpoint `
    -ModelDeploymentName $config.ModelDeploymentName `
    -McpServerUrl $mcpServerUrl `
    -ConnectionName $config.McpConnectionName `
    -AgentName $config.AgentName `
    -PythonExecutable $PythonExecutable `
    -SkipAgentSmokeTest:$config.SkipAgentSmokeTest `
    -ValidateOnly:$ValidateOnly

if ($ValidateOnly) {
    Write-Host "The full Azure pipeline configuration is valid. No Azure resources were changed."
} else {
    Write-Host "Full deployment completed: Azure Function, Foundry project/model, MCP connection, agent, and smoke test."
}
