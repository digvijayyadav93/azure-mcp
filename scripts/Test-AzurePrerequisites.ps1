[CmdletBinding()]
param(
    [switch]$SkipLoginCheck,
    [switch]$SkipToolCheck
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$requiredCommands = @(
    @{ Name = "python"; Install = "Install Python 3.13 and add it to PATH." },
    @{ Name = "az"; Install = "Install Azure CLI: https://aka.ms/installazurecliwindows" },
    @{ Name = "func"; Install = "Install Azure Functions Core Tools v4." },
    @{ Name = "azd"; Install = "Install Azure Developer CLI: https://aka.ms/install-azd" }
)

$missing = @()
if (-not $SkipToolCheck) {
    foreach ($item in $requiredCommands) {
        if (-not (Get-Command $item.Name -ErrorAction SilentlyContinue)) {
            $missing += "$($item.Name): $($item.Install)"
        }
    }
}

if ($missing.Count -gt 0) {
    throw "Missing prerequisites:`n$($missing -join "`n")"
}

if (-not $SkipToolCheck) {
    Write-Host "Required command-line tools are installed."
}

if (-not $SkipLoginCheck) {
    $null = & az account show --only-show-errors --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI is not signed in. Run: az login"
    }

    $null = & azd auth login --check-status --no-prompt
    if ($LASTEXITCODE -ne 0) {
        throw "Azure Developer CLI is not signed in. Run: azd auth login"
    }

    $null = & azd ai connection version --no-prompt
    if ($LASTEXITCODE -ne 0) {
        throw "Foundry azd extensions are missing. Run: azd ext install microsoft.foundry"
    }
    Write-Host "Azure CLI and Azure Developer CLI authentication are ready."
}
