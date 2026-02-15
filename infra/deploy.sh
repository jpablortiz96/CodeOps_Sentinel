#!/bin/bash
# =============================================================================
# CodeOps Sentinel — Azure Deployment Script (Bash)
# Usage: ./infra/deploy.sh
# Requirements: az CLI, docker
# =============================================================================
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
RESOURCE_GROUP="CodeOpsSentinel-rg"
LOCATION="${AZURE_LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-codeopssentinelacr}"
BACKEND_APP="${BACKEND_APP:-codeops-sentinel-api}"
AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-}"
AZURE_OPENAI_KEY="${AZURE_OPENAI_KEY:-}"
AZURE_OPENAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-gpt-4o}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "${RED}❌ $*${NC}"; exit 1; }
step() { echo -e "\n${YELLOW}▶ $*${NC}"; }

echo "============================================================"
echo "  CodeOps Sentinel — Azure Deployment"
echo "  Resource Group : $RESOURCE_GROUP"
echo "  Location       : $LOCATION"
echo "  ACR            : $ACR_NAME"
echo "============================================================"

# ── Prerequisites ──────────────────────────────────────────────────────────────
step "Checking prerequisites..."
command -v az     &>/dev/null || err "Azure CLI not found. Install: https://aka.ms/installazurecliwindows"
command -v docker &>/dev/null || warn "Docker not found — image builds will be done via ACR Tasks"

az account show &>/dev/null || err "Not logged into Azure. Run: az login"
SUBSCRIPTION=$(az account show --query name -o tsv)
ok "Azure CLI authenticated — subscription: $SUBSCRIPTION"

# ── Resource Group ─────────────────────────────────────────────────────────────
step "Step 1/8 — Ensuring Resource Group..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none 2>/dev/null || true
ok "Resource Group: $RESOURCE_GROUP"

# ── Deploy Bicep Infrastructure ────────────────────────────────────────────────
step "Step 2/8 — Deploying Azure infrastructure (Bicep)..."
DEPLOY_OUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$SCRIPT_DIR/main.bicep" \
    --parameters \
        azureOpenAiEndpoint="$AZURE_OPENAI_ENDPOINT" \
        azureOpenAiKey="$AZURE_OPENAI_KEY" \
        azureOpenAiDeployment="$AZURE_OPENAI_DEPLOYMENT" \
        acrName="$ACR_NAME" \
        backendAppName="$BACKEND_APP" \
    --query "properties.outputs" \
    --output json)

ACR_SERVER=$(echo "$DEPLOY_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['acrLoginServer']['value'])")
BACKEND_URL=$(echo "$DEPLOY_OUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['backendUrl']['value'])")
ok "Infrastructure deployed!"
ok "ACR: $ACR_SERVER"
ok "Backend URL: $BACKEND_URL"

# ── Build & Push Backend Image ─────────────────────────────────────────────────
step "Step 3/8 — Building backend image (ACR Tasks)..."
az acr build \
    --registry "$ACR_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --image "codeops-backend:latest" \
    --image "codeops-backend:$(date +%Y%m%d-%H%M%S)" \
    "$ROOT_DIR/backend"
ok "Backend image built and pushed"

# ── Build & Push Frontend Image ────────────────────────────────────────────────
step "Step 4/8 — Building frontend image (ACR Tasks)..."
az acr build \
    --registry "$ACR_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --image "codeops-frontend:latest" \
    "$ROOT_DIR/frontend"
ok "Frontend image built and pushed"

# ── Configure Backend App Settings ────────────────────────────────────────────
step "Step 5/8 — Configuring backend App Settings..."
az webapp config appsettings set \
    --name "$BACKEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        AZURE_OPENAI_ENDPOINT="$AZURE_OPENAI_ENDPOINT" \
        AZURE_OPENAI_KEY="$AZURE_OPENAI_KEY" \
        AZURE_OPENAI_DEPLOYMENT="$AZURE_OPENAI_DEPLOYMENT" \
        SIMULATION_MODE="$([ -z "$AZURE_OPENAI_KEY" ] && echo true || echo false)" \
        APP_ENV="production" \
    --output none
ok "App Settings configured"

# ── Enable WebSockets ──────────────────────────────────────────────────────────
step "Step 6/8 — Enabling WebSockets on backend..."
az webapp config set \
    --name "$BACKEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --web-sockets-enabled true \
    --output none
ok "WebSockets enabled"

# ── Restart backend ────────────────────────────────────────────────────────────
step "Step 7/8 — Restarting backend to pick up new image..."
az webapp restart \
    --name "$BACKEND_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --output none
ok "Backend restarted"

# ── Health check ───────────────────────────────────────────────────────────────
step "Step 8/8 — Waiting for health check..."
MAX_RETRIES=12; RETRY=0
until curl -sf "${BACKEND_URL}/health" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='healthy' else 1)" 2>/dev/null; do
    RETRY=$((RETRY+1))
    [ $RETRY -ge $MAX_RETRIES ] && err "Health check failed after ${MAX_RETRIES} retries"
    echo "  Waiting for backend... (${RETRY}/${MAX_RETRIES})"
    sleep 10
done
ok "Backend is healthy!"

echo ""
echo "============================================================"
echo "  🚀 DEPLOYMENT COMPLETE"
echo "  Backend  : ${BACKEND_URL}"
echo "  API Docs : ${BACKEND_URL}/docs"
echo "  Health   : ${BACKEND_URL}/health"
echo "============================================================"
