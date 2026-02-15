# =============================================================================
# CodeOps Sentinel - Frontend Deploy Script (Azure Static Web Apps)
# Usage: .\infra\deploy-frontend.ps1
# Requirements: Azure CLI (az), Node.js 20+
# =============================================================================
[CmdletBinding()]
param(
    [string]$ResourceGroup = "CodeOpsSentinel-rg",
    [string]$AppName       = "codeops-sentinel-app",
    [string]$Location      = "eastus2"
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = Split-Path -Parent $ScriptDir
$FrontDir  = Join-Path $RootDir "frontend"

function Write-Step { param($msg) Write-Host "`n>>> $msg" -ForegroundColor Yellow }
function Write-Ok   { param($msg) Write-Host "[OK] $msg"  -ForegroundColor Green  }
function Write-Warn { param($msg) Write-Host "[!!] $msg"  -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "[XX] $msg"  -ForegroundColor Red; exit 1 }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CodeOps Sentinel - Frontend Deploy (Static Web Apps)"      -ForegroundColor Cyan
Write-Host "  App Name       : $AppName"                                  -ForegroundColor Cyan
Write-Host "  Resource Group : $ResourceGroup"                            -ForegroundColor Cyan
Write-Host "  Location       : $Location"                                 -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# =============================================================================
# Step 1 - Check prerequisites
# =============================================================================
Write-Step "Step 1/5 - Checking prerequisites"

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Fail "Azure CLI not found. Install from: https://aka.ms/installazurecliwindows"
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Fail "Node.js not found. Install from: https://nodejs.org"
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Fail "npm not found. Install Node.js from: https://nodejs.org"
}

$account = az account show --query "name" -o tsv --only-show-errors 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Not logged into Azure. Run: az login"
}
Write-Ok "Azure CLI authenticated - Subscription: $account"

$nodeVer = node --version
Write-Ok "Node.js: $nodeVer"

# =============================================================================
# Step 2 - Install dependencies and build
# =============================================================================
Write-Step "Step 2/5 - Installing dependencies and building frontend"
Write-Host "  Directory: $FrontDir" -ForegroundColor Gray

Push-Location $FrontDir

npm install --silent
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Fail "npm install failed."
}
Write-Ok "Dependencies installed"

npm run build
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Fail "npm run build failed. Fix build errors and re-run."
}
Write-Ok "Frontend built successfully -> $FrontDir\dist"

Pop-Location

# =============================================================================
# Step 3 - Create Static Web App (if it doesn't exist)
# =============================================================================
Write-Step "Step 3/5 - Ensuring Static Web App exists"

az staticwebapp show --name $AppName --resource-group $ResourceGroup --output none --only-show-errors 2>$null
$swaExists = ($LASTEXITCODE -eq 0)

if ($swaExists) {
    Write-Host "  Static Web App already exists - skipping creation" -ForegroundColor Gray
} else {
    Write-Host "  Creating Static Web App '$AppName' in $Location..." -ForegroundColor Gray

    az staticwebapp create `
        --name $AppName `
        --resource-group $ResourceGroup `
        --location $Location `
        --output none --only-show-errors 2>$null

    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to create Static Web App."
    }
    Write-Ok "Static Web App created: $AppName"
}

# =============================================================================
# Step 4 - Deploy using Azure CLI
# =============================================================================
Write-Step "Step 4/5 - Deploying build to Static Web Apps"

# Get the deployment token
$Token = az staticwebapp secrets list `
    --name $AppName `
    --resource-group $ResourceGroup `
    --query "properties.apiKey" `
    --output tsv --only-show-errors 2>$null

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($Token)) {
    Write-Fail "Failed to retrieve deployment token."
}
Write-Ok "Deployment token obtained"

# Install SWA CLI if not present
$swaInstalled = Get-Command swa -ErrorAction SilentlyContinue
if (-not $swaInstalled) {
    Write-Host "  Installing SWA CLI globally..." -ForegroundColor Gray
    npm install -g @azure/static-web-apps-cli --silent
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to install SWA CLI."
    }
    Write-Ok "SWA CLI installed"
}

# Deploy the dist folder
Write-Host "  Deploying dist/ to Azure Static Web Apps..." -ForegroundColor Gray
swa deploy "$FrontDir\dist" `
    --deployment-token "$Token" `
    --no-use-keychain

if ($LASTEXITCODE -ne 0) {
    Write-Fail "SWA deploy failed."
}
Write-Ok "Frontend deployed successfully"

# =============================================================================
# Step 5 - Print final URL
# =============================================================================
Write-Step "Step 5/5 - Retrieving final URL"

$FrontendUrl = az staticwebapp show `
    --name $AppName `
    --resource-group $ResourceGroup `
    --query "properties.defaultHostname" `
    --output tsv --only-show-errors 2>$null

if ([string]::IsNullOrEmpty($FrontendUrl)) {
    $FrontendUrl = "Check Azure portal for $AppName hostname"
} else {
    $FrontendUrl = "https://$FrontendUrl"
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  FRONTEND DEPLOYMENT COMPLETE"                               -ForegroundColor Green
Write-Host "  URL      : $FrontendUrl"                                    -ForegroundColor Green
Write-Host "  Backend  : https://codeops-sentinel-api.wonderfulocean-93fc426c.eastus.azurecontainerapps.io" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Open $FrontendUrl in your browser"
Write-Host "  2. Backend CORS already allows azurestaticapps.net origins"
Write-Host "  3. If you see CORS errors, add the exact frontend URL to backend FRONTEND_URL env var:"
Write-Host "     az containerapp update --name codeops-sentinel-api --resource-group CodeOpsSentinel-rg --set-env-vars FRONTEND_URL=$FrontendUrl"
