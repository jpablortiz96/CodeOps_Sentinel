# Setup Guide — CodeOps Sentinel

## Local Development (Simulation Mode)

This mode requires no Azure or GitHub credentials. All external calls are mocked.

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env (simulation mode is default)
cp .env.example .env

# Start the API server
uvicorn app.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/health`

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Open `http://localhost:3000`

---

## Production Setup (Real Azure APIs)

### Prerequisites

1. Azure subscription with these services provisioned:
   - Azure OpenAI Service with GPT-4o deployment
   - Azure Log Analytics Workspace
   - Azure App Service (for backend)
   - Azure Static Web Apps (for frontend)

2. GitHub account with:
   - Personal Access Token with `repo` scope
   - Repository to monitor

### Configuration

```bash
cp .env.example backend/.env
```

Edit `backend/.env`:

```env
SIMULATION_MODE=false

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_KEY=<your-key>
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Azure Monitor
AZURE_SUBSCRIPTION_ID=<your-subscription-id>
AZURE_RESOURCE_GROUP=<your-resource-group>
AZURE_MONITOR_WORKSPACE=<log-analytics-workspace-id>

# GitHub
GITHUB_TOKEN=ghp_<your-pat>
GITHUB_REPO=your-org/your-repo
```

### Deploy to Azure

```bash
# Login
az login

# Deploy infrastructure and application
chmod +x infra/deploy.sh
./infra/deploy.sh production
```

---

## Docker

```bash
# Build and run full stack
docker-compose up --build

# Backend only
docker build -t sentinel-backend ./backend
docker run -p 8000:8000 --env-file backend/.env sentinel-backend

# Frontend only
docker build -t sentinel-frontend ./frontend
docker run -p 3000:3000 sentinel-frontend
```

---

## GitHub Actions CI/CD

Add these secrets to your GitHub repository:

| Secret | Description |
|--------|-------------|
| `AZURE_CREDENTIALS` | Azure service principal JSON |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_RESOURCE_GROUP` | Resource group name |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Static Web Apps deployment token |

The CI/CD pipeline (`ci-cd.yml`) automatically:
1. Runs Python tests and linting on every PR
2. Builds and validates the React app
3. On merge to `main`: builds Docker images, pushes to GHCR, deploys to Azure

---

## Troubleshooting

**Backend won't start**
```bash
# Check Python version
python --version  # Needs 3.12+

# Re-install dependencies
pip install -r requirements.txt --upgrade
```

**Frontend can't connect to backend**
- Ensure backend is running on port 8000
- Check browser console for CORS errors
- Vite proxy (`vite.config.js`) handles `/api` and `/ws` forwarding automatically in dev

**WebSocket shows "Offline"**
- Backend must be running and healthy
- Check `http://localhost:8000/health`
- The frontend auto-reconnects every 3 seconds

**Simulation incidents not progressing**
- Check backend logs for errors
- Verify `SIMULATION_MODE=true` in `.env`
- Each incident runs as a background task; check `uvicorn` output
