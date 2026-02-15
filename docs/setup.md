# CodeOps Sentinel — Deployment Guide

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Azure CLI | ≥ 2.60 | https://aka.ms/installazurecliwindows |
| Docker Desktop | ≥ 24 | https://www.docker.com/products/docker-desktop |
| Node.js | 20 LTS | https://nodejs.org |
| Python | 3.12+ | https://python.org |
| PowerShell | 7+ | Pre-installed on Windows 11 |

You also need:
- An **Azure Subscription** with Contributor rights on `CodeOpsSentinel-rg`
- An **Azure OpenAI** resource with a `gpt-4o` deployment (or set `SIMULATION_MODE=true`)

---

## Environment Variables

Create `backend/.env`:

```
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_KEY=your-api-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
SIMULATION_MODE=false
GITHUB_TOKEN=ghp_yourtoken
GITHUB_REPO=your-org/your-repo
APP_ENV=development
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Real AI only | — | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_KEY` | Real AI only | — | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | No | gpt-4o | Model deployment name |
| `SIMULATION_MODE` | No | true | false = real Azure OpenAI |
| `GITHUB_TOKEN` | No | — | For GitHub patch integration |
| `FRONTEND_URL` | No | — | Custom domain for CORS |

---

## Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

- Dashboard: http://localhost:5173
- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

---

## Deploy to Azure — One Command

**Windows (PowerShell — RECOMMENDED):**

```powershell
$env:AZURE_OPENAI_ENDPOINT = "https://your-instance.openai.azure.com/"
$env:AZURE_OPENAI_KEY      = "your-api-key"
az login
.\infra\deploy.ps1
```

**Linux/macOS (Bash):**

```bash
export AZURE_OPENAI_ENDPOINT="https://your-instance.openai.azure.com/"
export AZURE_OPENAI_KEY="your-api-key"
az login
chmod +x infra/deploy.sh && ./infra/deploy.sh
```

The script performs 8 steps automatically:

1. Validates Azure CLI login
2. Creates/updates `CodeOpsSentinel-rg` resource group
3. Deploys all Azure resources via Bicep (ACR, App Service Plan, App Service, App Insights, Log Analytics)
4. Builds backend Docker image via **ACR Tasks** (no local Docker required)
5. Builds frontend Docker image via **ACR Tasks**
6. Configures all App Settings including secrets
7. Enables WebSockets + restarts App Service
8. Polls `/health` until backend reports `healthy`

---

## CI/CD Setup (GitHub Actions)

### Required Secrets

Go to **GitHub repo → Settings → Secrets and variables → Actions**:

| Secret | How to get |
|--------|------------|
| `AZURE_CREDENTIALS` | `az ad sp create-for-rbac --sdk-auth` (see below) |
| `AZURE_OPENAI_ENDPOINT` | Your Azure OpenAI endpoint |
| `AZURE_OPENAI_KEY` | Your Azure OpenAI API key |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | `az staticwebapp secrets list --name ...` |

```bash
# Create service principal
az ad sp create-for-rbac \
  --name "codeops-sentinel-cicd" \
  --role Contributor \
  --scopes /subscriptions/<SUB_ID>/resourceGroups/CodeOpsSentinel-rg \
  --sdk-auth
# Copy the JSON output → AZURE_CREDENTIALS secret
```

After adding secrets, any push to `main` triggers the full pipeline.

---

## Troubleshooting

**WebSocket disconnects in Azure:**
```bash
az webapp config set --name codeops-sentinel-api \
  --resource-group CodeOpsSentinel-rg --web-sockets-enabled true
```

**View backend logs:**
```bash
az webapp log tail --name codeops-sentinel-api \
  --resource-group CodeOpsSentinel-rg
```

**ACR name already taken:** ACR names are globally unique — pass a custom name:
```powershell
.\infra\deploy.ps1 -AcrName "myuniquename123"
```

**Frontend can't reach backend:** Set `FRONTEND_URL=https://your-app.azurestaticapps.net`
in the backend App Service → Configuration → Application settings.
