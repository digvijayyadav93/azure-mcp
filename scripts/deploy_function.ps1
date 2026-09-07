[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$SubscriptionId,
    [Parameter(Mandatory)] [string]$Location,
    [Parameter(Mandatory)] [string]$ResourceGroupName,
    [Parameter(Mandatory)] [string]$StorageAccountName,
    [Parameter(Mandatory)] [string]$FunctionAppName,
    [string]$PythonVersion = "3.13",
    [bool]$UseApi = $false,
    [string]$DbApiBaseUrl = "",
    [string]$PythonExecutable = "python",
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-CommandSucceeded([string]$Description) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

if ($SubscriptionId -notmatch '^[0-9a-fA-F-]{36}$') {
    throw "SubscriptionId must be an Azure subscription GUID."
}
if ($StorageAccountName -notmatch '^[a-z0-9]{3,24}$') {
    throw "StorageAccountName must contain 3-24 lowercase letters or numbers."
}
if ($FunctionAppName -notmatch '^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$') {
    throw "FunctionAppName must contain 3-60 lowercase letters, numbers, or hyphens and cannot end with a hyphen."
}
if ($UseApi -and $DbApiBaseUrl -notmatch '^https://') {
    throw "DbApiBaseUrl must be an HTTPS URL when UseApi=true."
}
if (-not $env:MCP_API_KEY -or $env:MCP_API_KEY.Length -lt 16) {
    throw "Set MCP_API_KEY to a random value of at least 16 characters before deployment."
}
if (-not $env:DB_API_KEY -or $env:DB_API_KEY.Length -lt 16) {
    throw "Set DB_API_KEY to a random value of at least 16 characters before deployment."
}

if ($ValidateOnly) {
    Write-Host "Azure Function configuration is valid. No Azure changes were made."
    return
}

$null = & az account set --subscription $SubscriptionId
Assert-CommandSucceeded "Selecting the Azure subscription"

$supportedLocations = @(& az functionapp list-flexconsumption-locations --query "[].name" --output tsv)
Assert-CommandSucceeded "Listing Flex Consumption locations"
if ($Location -notin $supportedLocations) {
    throw "Location '$Location' is not currently listed for Flex Consumption. Supported values: $($supportedLocations -join ', ')"
}

$null = & az group show --name $ResourceGroupName --only-show-errors --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating resource group $ResourceGroupName..."
    $null = & az group create --name $ResourceGroupName --location $Location --output none
    Assert-CommandSucceeded "Creating the resource group"
}

$null = & az storage account show --name $StorageAccountName --resource-group $ResourceGroupName --only-show-errors --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating storage account $StorageAccountName..."
    $null = & az storage account create `
        --name $StorageAccountName `
        --resource-group $ResourceGroupName `
        --location $Location `
        --sku Standard_LRS `
        --allow-blob-public-access false `
        --output none
    Assert-CommandSucceeded "Creating the storage account"
}

$null = & az functionapp show --name $FunctionAppName --resource-group $ResourceGroupName --only-show-errors --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Flex Consumption Function App $FunctionAppName..."
    $null = & az functionapp create `
        --name $FunctionAppName `
        --resource-group $ResourceGroupName `
        --storage-account $StorageAccountName `
        --flexconsumption-location $Location `
        --runtime python `
        --runtime-version $PythonVersion `
        --functions-version 4 `
        --output none
    Assert-CommandSucceeded "Creating the Function App"
}

$useApiValue = $UseApi.ToString().ToLowerInvariant()
$appSettings = @(
    "MCP_API_KEY=$($env:MCP_API_KEY)",
    "DB_API_KEY=$($env:DB_API_KEY)",
    "USE_API=$useApiValue",
    "MCP_HOST=0.0.0.0"
)
if ($UseApi) {
    $appSettings += "DB_API_BASE_URL=$DbApiBaseUrl"
}

Write-Host "Applying Function App settings..."
$null = & az functionapp config appsettings set `
    --name $FunctionAppName `
    --resource-group $ResourceGroupName `
    --settings @appSettings `
    --output none
Assert-CommandSucceeded "Applying Function App settings"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    Write-Host "Publishing Python code with a remote build..."
    & func azure functionapp publish $FunctionAppName --python
    Assert-CommandSucceeded "Publishing the Function App"

    $baseUrl = "https://$FunctionAppName.azurewebsites.net"
    $healthy = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get -TimeoutSec 20
            if ($health.status -eq "ok") {
                $healthy = $true
                break
            }
        }
        catch {
            Write-Host "Waiting for Function App startup ($attempt/30)..."
        }
        Start-Sleep -Seconds 10
    }
    if (-not $healthy) {
        throw "Function App did not pass its health check within five minutes."
    }

    Write-Host "Running the deployed MCP protocol smoke test..."
    & $PythonExecutable scripts\smoke_test.py `
        --url "$baseUrl/mcp" `
        --api-key $env:MCP_API_KEY `
        --customer-id 1
    Assert-CommandSucceeded "Testing the deployed MCP endpoint"
}
finally {
    Pop-Location
}

Write-Host "Function deployment passed. MCP endpoint: https://$FunctionAppName.azurewebsites.net/mcp"
