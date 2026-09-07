[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$SubscriptionId,
    [Parameter(Mandatory)] [string]$Location,
    [Parameter(Mandatory)] [string]$ResourceGroupName,
    [Parameter(Mandatory)] [string]$FoundryResourceName,
    [Parameter(Mandatory)] [string]$FoundryProjectName,
    [Parameter(Mandatory)] [string]$ModelDeploymentName,
    [Parameter(Mandatory)] [string]$ModelName,
    [Parameter(Mandatory)] [string]$ModelVersion,
    [string]$ModelFormat = "OpenAI",
    [string]$ModelSkuName = "GlobalStandard",
    [int]$ModelSkuCapacity = 10,
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
if ($FoundryResourceName -notmatch '^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$') {
    throw "FoundryResourceName must contain 3-64 lowercase letters, numbers, or hyphens."
}
if ($FoundryProjectName -notmatch '^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,62}[a-zA-Z0-9]$') {
    throw "FoundryProjectName must contain 3-64 letters, numbers, dots, underscores, or hyphens."
}
foreach ($value in @($ModelDeploymentName, $ModelName, $ModelVersion, $ModelFormat, $ModelSkuName)) {
    if ($value -notmatch '^[a-zA-Z0-9._-]+$') {
        throw "Model names, versions, formats, and SKUs may contain only letters, numbers, dots, underscores, or hyphens."
    }
}
if ($ModelSkuCapacity -lt 1) {
    throw "ModelSkuCapacity must be at least 1."
}

if ($ValidateOnly) {
    $previewEndpoint = "https://$FoundryResourceName.services.ai.azure.com/api/projects/$FoundryProjectName"
    Write-Host "Foundry configuration is valid. No Azure changes were made."
    Write-Output $previewEndpoint
    return
}

$null = & az account set --subscription $SubscriptionId
Assert-CommandSucceeded "Selecting the Azure subscription"

$null = & az group show --name $ResourceGroupName --only-show-errors --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    $null = & az group create --name $ResourceGroupName --location $Location --output none
    Assert-CommandSucceeded "Creating the resource group"
}

$null = & az cognitiveservices account show `
    --name $FoundryResourceName `
    --resource-group $ResourceGroupName `
    --only-show-errors `
    --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Foundry resource $FoundryResourceName..."
    $null = & az cognitiveservices account create `
        --name $FoundryResourceName `
        --resource-group $ResourceGroupName `
        --kind AIServices `
        --sku S0 `
        --location $Location `
        --custom-domain $FoundryResourceName `
        --allow-project-management `
        --output none
    Assert-CommandSucceeded "Creating the Foundry resource"
}

$null = & az cognitiveservices account project show `
    --name $FoundryResourceName `
    --resource-group $ResourceGroupName `
    --project-name $FoundryProjectName `
    --only-show-errors `
    --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Foundry project $FoundryProjectName..."
    $null = & az cognitiveservices account project create `
        --name $FoundryResourceName `
        --resource-group $ResourceGroupName `
        --project-name $FoundryProjectName `
        --location $Location `
        --output none
    Assert-CommandSucceeded "Creating the Foundry project"
}

$null = & az cognitiveservices account deployment show `
    --name $FoundryResourceName `
    --resource-group $ResourceGroupName `
    --deployment-name $ModelDeploymentName `
    --only-show-errors `
    --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    $modelQuery = "[?model.name=='$ModelName' && model.version=='$ModelVersion'] | [0].model.name"
    $availableModel = & az cognitiveservices model list `
        --location $Location `
        --query $modelQuery `
        --output tsv
    Assert-CommandSucceeded "Checking regional model availability"
    if (-not $availableModel) {
        throw "Model $ModelName version $ModelVersion is not available in $Location. Run 'az cognitiveservices model list --location $Location --output table' and update azure/config.psd1."
    }

    Write-Host "Deploying model $ModelDeploymentName..."
    $null = & az cognitiveservices account deployment create `
        --name $FoundryResourceName `
        --resource-group $ResourceGroupName `
        --deployment-name $ModelDeploymentName `
        --model-name $ModelName `
        --model-version $ModelVersion `
        --model-format $ModelFormat `
        --sku-name $ModelSkuName `
        --sku-capacity $ModelSkuCapacity `
        --output none
    Assert-CommandSucceeded "Deploying the Foundry model"
}

$deploymentState = & az cognitiveservices account deployment show `
    --name $FoundryResourceName `
    --resource-group $ResourceGroupName `
    --deployment-name $ModelDeploymentName `
    --query properties.provisioningState `
    --output tsv
Assert-CommandSucceeded "Verifying the model deployment"
if ($deploymentState -ne "Succeeded") {
    throw "Model deployment state is '$deploymentState', not 'Succeeded'."
}

$endpointQuery = 'properties.endpoints."AI Foundry API"'
$projectEndpoint = & az cognitiveservices account project show `
    --name $FoundryResourceName `
    --resource-group $ResourceGroupName `
    --project-name $FoundryProjectName `
    --query $endpointQuery `
    --output tsv
Assert-CommandSucceeded "Reading the Foundry project endpoint"
if (-not $projectEndpoint) {
    $projectEndpoint = "https://$FoundryResourceName.services.ai.azure.com/api/projects/$FoundryProjectName"
}

Write-Host "Foundry provisioning passed. Project endpoint: $projectEndpoint"
Write-Output $projectEndpoint
