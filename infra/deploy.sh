#!/bin/bash
# CodeOps Sentinel - Azure Deployment Script
# Usage: ./infra/deploy.sh [environment]

set -euo pipefail

ENVIRONMENT=${1:-"production"}
RESOURCE_GROUP="codeops-sentinel-rg"
LOCATION="eastus2"
APP_NAME="codeops-sentinel"

echo "================================================================"
echo "  CodeOps Sentinel - Azure Deployment"
echo "  Environment: $ENVIRONMENT | Region: $LOCATION"
echo "================================================================"

# Check Azure CLI login
if ! az account show &>/dev/null; then
    echo "❌ Not logged into Azure. Run: az login"
    exit 1
fi

echo "✅ Azure CLI authenticated"
SUBSCRIPTION=$(az account show --query name -o tsv)
echo "   Subscription: $SUBSCRIPTION"

# Create resource group
echo ""
echo "📦 Creating resource group..."
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --tags project=codeops-sentinel environment="$ENVIRONMENT" \
    --output none
echo "✅ Resource group: $RESOURCE_GROUP"

# Deploy Bicep infrastructure
echo ""
echo "🏗️  Deploying Azure infrastructure (Bicep)..."
DEPLOY_OUTPUT=$(az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$(dirname "$0")/main.bicep" \
    --parameters appEnv="$ENVIRONMENT" \
    --query "properties.outputs" \
    --output json)

BACKEND_URL=$(echo "$DEPLOY_OUTPUT" | jq -r '.backendUrl.value')
FRONTEND_URL=$(echo "$DEPLOY_OUTPUT" | jq -r '.frontendUrl.value')

echo "✅ Infrastructure deployed!"
echo "   Backend:  $BACKEND_URL"
echo "   Frontend: $FRONTEND_URL"

# Build & push Docker images
echo ""
echo "🐳 Building Docker images..."
REGISTRY="ghcr.io/$(git config --get remote.origin.url | sed 's/.*github.com\///' | sed 's/\.git//')"
GIT_SHA=$(git rev-parse --short HEAD)

docker build -t "${REGISTRY}/sentinel-backend:${GIT_SHA}" -t "${REGISTRY}/sentinel-backend:latest" ./backend
docker build -t "${REGISTRY}/sentinel-frontend:${GIT_SHA}" -t "${REGISTRY}/sentinel-frontend:latest" ./frontend
docker push "${REGISTRY}/sentinel-backend:${GIT_SHA}"
docker push "${REGISTRY}/sentinel-frontend:${GIT_SHA}"
echo "✅ Images pushed to registry"

echo ""
echo "================================================================"
echo "  🚀 Deployment Complete!"
echo "  Backend:  $BACKEND_URL/health"
echo "  Frontend: $FRONTEND_URL"
echo "  Docs:     $BACKEND_URL/docs"
echo "================================================================"
