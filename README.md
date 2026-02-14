# CodeOps Sentinel

**Multi-Agent Auto-Remediation Platform for DevOps**

> An AI-powered platform that detects, diagnoses, fixes, and deploys solutions to production incidents — autonomously.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CodeOps Sentinel                            │
│                                                                 │
│  ┌──────────┐    ┌────────────┐    ┌────────┐    ┌─────────┐  │
│  │  Monitor  │───▶│ Diagnostic │───▶│ Fixer  │───▶│ Deploy  │  │
│  │  Agent   │    │   Agent    │    │ Agent  │    │  Agent  │  │
│  │          │    │            │    │        │    │         │  │
│  │Azure Mon │    │Azure OpenAI│    │GitHub  │    │Azure    │  │
│  │Log Query │    │GPT-4o RCA  │    │Copilot │    │DevOps   │  │
│  └──────────┘    └────────────┘    └────────┘    └─────────┘  │
│        │               │               │              │        │
│        └───────────────┴───────────────┴──────────────┘        │
│                              │                                  │
│                   ┌──────────▼──────────┐                      │
│                   │  OrchestratorAgent  │                      │
│                   │  (State Machine)    │                      │
│                   │  Azure MCP Server   │                      │
│                   └─────────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
         │                                          │
    FastAPI + WS                              React Dashboard
    (Port 8000)                               (Port 3000)
```

### State Machine

```
DETECTED → DIAGNOSING → FIXING → DEPLOYING → RESOLVED
                                     └──────→ ROLLED_BACK
```

---

## Technologies

| Layer | Technology |
|-------|-----------|
| **AI Orchestration** | Azure AI Foundry (GPT-4o) |
| **Agent Communication** | Azure MCP Server |
| **Code Intelligence** | GitHub Copilot Agent Mode |
| **Monitoring** | Azure Monitor + Log Analytics |
| **Backend** | Python FastAPI + WebSockets |
| **Frontend** | React 18 + Vite + Tailwind CSS |
| **Infrastructure** | Azure Bicep (IaC) |
| **CI/CD** | GitHub Actions |
| **Containers** | Docker + Azure App Service |
| **Static Hosting** | Azure Static Web Apps |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 20+
- Docker (optional)

### 1. Backend

```bash
cd backend
pip install -r requirements.txt

# Copy and configure environment (simulation mode works out of the box)
cp .env.example .env

# Run the API
uvicorn app.main:app --reload --port 8000
```

API available at: `http://localhost:8000`
Swagger docs: `http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at: `http://localhost:3000`

### 3. Docker Compose (Full Stack)

```bash
docker-compose up --build
```

---

## Usage

1. Open `http://localhost:3000`
2. Click **"Simulate Incident"** or choose a specific scenario
3. Watch the 4 agents automatically remediate the incident in real time
4. View the **Timeline** for step-by-step agent actions
5. Check the **Agent Flow** to see which agent is currently active

### Available Scenarios

| Scenario | Service | Description |
|----------|---------|-------------|
| CPU Spike | payment-service | N+1 queries causing CPU saturation |
| Memory Leak | auth-service | Event listener not cleaned up |
| DB Pool | user-service | Connection pool exhausted |
| Latency | recommendation-service | Missing database index |
| CI/CD Fail | k8s-cluster | ImagePullBackOff on pods |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/incidents` | List all incidents |
| `GET` | `/api/incidents/{id}` | Get incident detail |
| `POST` | `/api/incidents/simulate` | Trigger simulation |
| `GET` | `/api/agents/status` | Agent statuses |
| `POST` | `/api/agents/trigger` | Trigger agent manually |
| `WS` | `/ws` | Real-time WebSocket feed |

---

## Project Structure

```
CodeOps_Sentinel/
├── backend/app/
│   ├── agents/          # 4 specialized AI agents
│   ├── services/        # Azure Monitor, GitHub, Foundry integrations
│   ├── models/          # Pydantic data models
│   └── api/             # FastAPI routes + WebSocket
├── frontend/src/
│   └── components/      # React dashboard components
├── infra/               # Azure Bicep IaC
└── .github/workflows/   # GitHub Actions CI/CD
```

---

## Azure Deployment

```bash
# Login to Azure
az login

# Deploy infrastructure + application
chmod +x infra/deploy.sh
./infra/deploy.sh production
```

---

## Configuration

Set these environment variables (see `.env.example`):

```bash
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_KEY=your-key
GITHUB_TOKEN=ghp_your_token
GITHUB_REPO=your-org/your-repo
SIMULATION_MODE=true  # false to use real APIs
```

---

## Team

Built for the Microsoft + GitHub AI Hackathon — leveraging the full Azure AI ecosystem for intelligent DevOps automation.

---

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)
![Azure](https://img.shields.io/badge/Azure-0078D4?style=flat&logo=microsoft-azure&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat&logo=github-actions&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.12-3776AB?style=flat&logo=python&logoColor=white)
