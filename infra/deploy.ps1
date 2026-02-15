# =============================================================================
# CodeOps Sentinel - Azure Deployment Script (PowerShell)
# Uses Azure Container Apps (no VM quota required).
# Usage: .\infra\deploy.ps1
# Requirements: Azure CLI (az), internet access for ACR Tasks
# =============================================================================
[CmdletBinding()]
param(
    [string]$ResourceGroup    = "CodeOpsSentinel-rg",
    [string]$Location         = "eastus",
    [string]$AcrName          = "codeopssentinelacr",
    [string]$BackendApp       = "codeops-sentinel-api",
    [string]$OpenAiEndpoint   = $env:AZURE_OPENAI_ENDPOINT,
    [string]$OpenAiDeployment = "gpt-4o",
    [string]$OpenAiKey        = $env:AZURE_OPENAI_KEY
)

$ErrorActionPreference = "Continue"  # "Stop" throws on any az stderr output (warnings, progress)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = Split-Path -Parent $ScriptDir

function Write-Step { param($msg) Write-Host "`n>>> $msg" -ForegroundColor Yellow }
function Write-Ok   { param($msg) Write-Host "[OK] $msg"  -ForegroundColor Green  }
function Write-Warn { param($msg) Write-Host "[!!] $msg"  -ForegroundColor Yellow }
function Write-Fail { param($msg) Write-Host "[XX] $msg"  -ForegroundColor Red; exit 1 }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CodeOps Sentinel - Azure Deployment (Container Apps)"      -ForegroundColor Cyan
Write-Host "  Resource Group : $ResourceGroup"                            -ForegroundColor Cyan
Write-Host "  Location       : $Location"                                 -ForegroundColor Cyan
Write-Host "  ACR Name       : $AcrName"                                  -ForegroundColor Cyan
Write-Host "  Backend App    : $BackendApp"                               -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# =============================================================================
# Step 1 - Check prerequisites
# =============================================================================
Write-Step "Step 1/8 - Checking prerequisites"

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Fail "Azure CLI not found. Install from: https://aka.ms/installazurecliwindows"
}

$account = az account show --query "name" -o tsv 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Not logged into Azure. Run: az login"
}
Write-Ok "Azure CLI authenticated - Subscription: $account"

# Ensure required resource providers are registered
az provider register --namespace Microsoft.App --wait --output none 2>$null
az provider register --namespace Microsoft.OperationalInsights --wait --output none 2>$null

# =============================================================================
# Step 2 - Resource Group
# =============================================================================
Write-Step "Step 2/8 - Ensuring Resource Group exists"

az group create `
    --name $ResourceGroup `
    --location $Location `
    --output none 2>$null

if ($LASTEXITCODE -ne 0) {
    Write-Warn "Resource group may already exist - continuing"
}
Write-Ok "Resource Group: $ResourceGroup"

# =============================================================================
# Step 3 - Deploy Bicep Infrastructure (env + ACR + monitoring, NO container app)
# =============================================================================
Write-Step "Step 3/8 - Deploying Azure infrastructure via Bicep"
Write-Host "  Provisions: Log Analytics, App Insights, ACR, Container Apps Environment" -ForegroundColor Gray
Write-Host "  This may take 3-6 minutes..." -ForegroundColor Gray

$deployJson = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file "$ScriptDir\main.bicep" `
    --parameters `
        acrName="$AcrName" `
        backendAppName="$BackendApp" `
    --query "properties.outputs" `
    --output json

if ($LASTEXITCODE -ne 0) {
    Write-Fail "Bicep deployment failed. Check the error above."
}

$deployOut        = $deployJson | ConvertFrom-Json
$AcrServer        = $deployOut.acrLoginServer.value
$ContainerEnvName = $deployOut.containerEnvName.value
$AppInsightsConn  = $deployOut.appInsightsConnStr.value
$BackendUrl       = $deployOut.backendUrl.value

Write-Ok "Infrastructure deployed successfully"
Write-Ok "ACR Login Server       : $AcrServer"
Write-Ok "Container Apps Env     : $ContainerEnvName"
Write-Ok "Backend URL (computed) : $BackendUrl"

# =============================================================================
# Step 4 - Build and Push Backend Image via ACR Tasks
# =============================================================================
Write-Step "Step 4/8 - Building backend Docker image (ACR Tasks - no local Docker needed)"

az acr build `
    --registry $AcrName `
    --resource-group $ResourceGroup `
    --image "codeops-backend:latest" `
    "$RootDir\backend"

if ($LASTEXITCODE -ne 0) {
    Write-Fail "Backend image build failed."
}
Write-Ok "Backend image built and pushed to ACR"

# =============================================================================
# Step 5 - Build and Push Frontend Image via ACR Tasks
# =============================================================================
Write-Step "Step 5/8 - Building frontend Docker image (ACR Tasks)"

az acr build `
    --registry $AcrName `
    --resource-group $ResourceGroup `
    --image "codeops-frontend:latest" `
    "$RootDir\frontend"

if ($LASTEXITCODE -ne 0) {
    Write-Fail "Frontend image build failed."
}
Write-Ok "Frontend image built and pushed to ACR"

# =============================================================================
# Step 6 - Create Container App (image now exists in ACR)
# =============================================================================
Write-Step "Step 6/8 - Creating Container App"

$SimMode    = if ([string]::IsNullOrEmpty($OpenAiKey)) { "true" } else { "false" }
$AcrPwd     = az acr credential show --name $AcrName --query "passwords[0].value" -o tsv --only-show-errors 2>$null
Write-Host "  SIMULATION_MODE = $SimMode" -ForegroundColor Gray

# Build env-vars list (all as KEY=VALUE strings, key is secretref for OpenAI)
$EnvVars = @(
    "APP_ENV=production",
    "APP_VERSION=2.0.0",
    "DEBUG=false",
    "SIMULATION_MODE=$SimMode",
    "AZURE_OPENAI_ENDPOINT=$OpenAiEndpoint",
    "AZURE_OPENAI_DEPLOYMENT=$OpenAiDeployment",
    "APPLICATIONINSIGHTS_CONNECTION_STRING=$AppInsightsConn",
    "WORKERS=2"
)

# Check if the Container App already exists (re-deploy case)
az containerapp show --name $BackendApp --resource-group $ResourceGroup --output none --only-show-errors 2>$null
$appExists = ($LASTEXITCODE -eq 0)

if ($appExists) {
    Write-Host "  Container App already exists - updating..." -ForegroundColor Gray

    az containerapp update `
        --name $BackendApp `
        --resource-group $ResourceGroup `
        --image "$AcrServer/codeops-backend:latest" `
        --set-env-vars @EnvVars `
        --output none --only-show-errors 2>$null

    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to update Container App."
    }
    Write-Ok "Container App updated"
} else {
    Write-Host "  Creating new Container App..." -ForegroundColor Gray

    # Add OpenAI key as a secret if provided
    if ([string]::IsNullOrEmpty($OpenAiKey)) {
        az containerapp create `
            --name $BackendApp `
            --resource-group $ResourceGroup `
            --environment $ContainerEnvName `
            --image "$AcrServer/codeops-backend:latest" `
            --registry-server $AcrServer `
            --registry-username $AcrName `
            --registry-password "$AcrPwd" `
            --target-port 8000 `
            --ingress external `
            --transport http `
            --min-replicas 1 `
            --max-replicas 3 `
            --cpu 0.5 `
            --memory 1.0Gi `
            --env-vars @EnvVars `
            --output none --only-show-errors 2>$null
    } else {
        $EnvVarsWithKey = $EnvVars + @("AZURE_OPENAI_KEY=secretref:openai-key")

        az containerapp create `
            --name $BackendApp `
            --resource-group $ResourceGroup `
            --environment $ContainerEnvName `
            --image "$AcrServer/codeops-backend:latest" `
            --registry-server $AcrServer `
            --registry-username $AcrName `
            --registry-password "$AcrPwd" `
            --target-port 8000 `
            --ingress external `
            --transport http `
            --min-replicas 1 `
            --max-replicas 3 `
            --cpu 0.5 `
            --memory 1.0Gi `
            --secrets "openai-key=$OpenAiKey" `
            --env-vars @EnvVarsWithKey `
            --output none --only-show-errors 2>$null
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Fail "Failed to create Container App."
    }
    Write-Ok "Container App created successfully"
}

# =============================================================================
# Step 7 - Confirm revision is running
# =============================================================================
Write-Step "Step 7/8 - Confirming active revision"

$revision = az containerapp revision list `
    --name $BackendApp `
    --resource-group $ResourceGroup `
    --query "[0].name" `
    --output tsv --only-show-errors 2>$null

Write-Ok "Active revision: $revision"

# =============================================================================
# Step 8 - Health Check
# =============================================================================
Write-Step "Step 8/8 - Waiting for backend health check"
Write-Host "  URL: $BackendUrl/health" -ForegroundColor Gray

$MaxRetries = 15
$Retry = 0
$IsHealthy = $false

while ($Retry -lt $MaxRetries) {
    $Retry++
    Start-Sleep -Seconds 10
    Write-Host "  Attempt $Retry/$MaxRetries ..." -ForegroundColor Gray

    try {
        $resp = Invoke-RestMethod -Uri "$BackendUrl/health" -Method Get -TimeoutSec 10 -ErrorAction Stop
        if ($resp.status -eq "healthy") {
            $IsHealthy = $true
            break
        }
        Write-Host "  Status: $($resp.status)" -ForegroundColor Gray
    }
    catch {
        Write-Host "  Not ready yet: $($_.Exception.Message)" -ForegroundColor Gray
    }
}

if (-not $IsHealthy) {
    Write-Warn "Health check did not pass after $MaxRetries attempts"
    Write-Host "  Check logs: az containerapp logs show --name $BackendApp --resource-group $ResourceGroup --follow" -ForegroundColor Yellow
} else {
    Write-Ok "Backend is healthy!"
}

# =============================================================================
# Done
# =============================================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  DEPLOYMENT COMPLETE"                                         -ForegroundColor Green
Write-Host "  Backend  : $BackendUrl"                                      -ForegroundColor Green
Write-Host "  API Docs : $BackendUrl/docs"                                 -ForegroundColor Green
Write-Host "  Health   : $BackendUrl/health"                               -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Open $BackendUrl/health to verify the deployment"
Write-Host "  2. Connect your frontend to: $BackendUrl"
Write-Host "  3. View logs: az containerapp logs show --name $BackendApp --resource-group $ResourceGroup --follow"
