[CmdletBinding()]
param(
    [string]$ConfigPath = "azureconfig.psd1",
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
    throw "Configuration file not found: $resolvedConfig. Copy azureconfig.psd1.example to azureconfig.psd1 and fill in the values."
}

$config = Import-PowerShellDataFile -LiteralPath $resolvedConfig
$requiredKeys = @(
    "SubscriptionId", "Location", "ResourceGroupName", "StorageAccountName",
    "FunctionAppName", "PythonVersion", "UseApi", "DbApiBaseUrl",
    "SqlConnectionString", "FoundryResourceName", "FoundryProjectName",
    "ModelDeploymentName", "ModelName", "ModelVersion", "ModelFormat",
    "ModelSkuName", "ModelSkuCapacity", "AgentName", "McpConnectionName",
    "SkipAgentSmokeTest"
)
foreach ($key in $requiredKeys) {
    if (-not $config.ContainsKey($key)) {
        throw "Missing '$key' in $resolvedConfig."
    }
}

& (Join-Path $PSScriptRoot "Test-AzurePrerequisites.ps1")     -SkipLoginCheck:$ValidateOnly     -SkipToolCheck:$ValidateOnly

& (Join-Path $PSScriptRoot "deploy_function.ps1")     -SubscriptionId $config.SubscriptionId     -Location $config.Location     -ResourceGroupName $config.ResourceGroupName     -StorageAccountName $config.StorageAccountName     -FunctionAppName $config.FunctionAppName     -PythonVersion $config.PythonVersion     -UseApi $config.UseApi     -DbApiBaseUrl $config.DbApiBaseUrl     -SqlConnectionString $config.SqlConnectionString     -PythonExecutable $PythonExecutable     -ValidateOnly:$ValidateOnly

$projectEndpoint = & (Join-Path $PSScriptRoot "provision_foundry.ps1")     -SubscriptionId $config.SubscriptionId     -Location $config.Location     -ResourceGroupName $config.ResourceGroupName     -FoundryResourceName $config.FoundryResourceName     -FoundryProjectName $config.FoundryProjectName     -ModelDeploymentName $config.ModelDeploymentName     -ModelName $config.ModelName     -ModelVersion $config.ModelVersion     -ModelFormat $config.ModelFormat     -ModelSkuName $config.ModelSkuName     -ModelSkuCapacity $config.ModelSkuCapacity     -ValidateOnly:$ValidateOnly

if ($ValidateOnly) {
    $mcpServerUrl = "https://validated-function-host.example/mcp"
} else {
    $defaultHostName = & az functionapp show         --name $config.FunctionAppName         --resource-group $config.ResourceGroupName         --query defaultHostName         --output tsv
    if ($LASTEXITCODE -ne 0 -or -not $defaultHostName) {
        throw "Could not read the deployed Function App hostname."
    }
    $mcpServerUrl = "https://$defaultHostName/mcp"
}

& (Join-Path $PSScriptRoot "configure_foundry.ps1")     -ProjectEndpoint $projectEndpoint     -ModelDeploymentName $config.ModelDeploymentName     -McpServerUrl $mcpServerUrl     -ConnectionName $config.McpConnectionName     -AgentName $config.AgentName     -PythonExecutable $PythonExecutable     -SkipAgentSmokeTest:$config.SkipAgentSmokeTest     -ValidateOnly:$ValidateOnly

if ($ValidateOnly) {
    Write-Host "The full Azure pipeline configuration is valid. No Azure resources were changed."
} else {
    Write-Host "Full deployment completed: Azure Function, Azure SQL, Foundry project/model, MCP connection, agent, and smoke test."
}
