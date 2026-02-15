# CodeOps Sentinel

![Build](https://github.com/your-org/CodeOps_Sentinel/actions/workflows/ci-cd.yml/badge.svg?branch=main)
![Azure](https://img.shields.io/badge/Azure-Deployed-0078D4?logo=microsoft-azure&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.12-3776AB?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React_18-61DAFB?logo=react&logoColor=black)
![License](https://img.shields.io/badge/License-MIT-green)

**Multi-Agent Auto-Remediation Platform for DevOps**

> An AI-powered platform that detects, diagnoses, fixes, and deploys solutions to production incidents — autonomously, in real time.
> Built for the **Microsoft + GitHub AI Hackathon** using the complete Azure AI ecosystem.

---

## 🦾 Hero Technologies

| Technology | Role |
|------------|------|
| ✅ **Microsoft AI Foundry** | GPT-4o model hosting, inference, and management |
| ✅ **Microsoft Agent Framework** | Multi-agent orchestration with A2A protocol |
| ✅ **Azure MCP Server** | Standardized agent-to-agent communication (JSON-RPC 2.0) |
| ✅ **GitHub Copilot Agent Mode** | AI-assisted code patch generation and review |
| ✅ **Azure Monitor / SRE Agent** | Real-time metrics ingestion and health monitoring |
| ✅ **Azure App Service** | Cloud deployment with WebSocket support |
| ✅ **Azure Container Registry** | Docker image storage and ACR Tasks builds |
| ✅ **GitHub Actions** | Automated CI/CD pipeline |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       CodeOps Sentinel v2.0                         │
│                                                                     │
│  ┌───────────┐  MCP   ┌────────────┐  MCP   ┌────────┐  MCP        │
│  │  Monitor  │──────▶│ Diagnostic │──────▶│ Fixer  │──────▶ ...   │
│  │  Agent    │        │   Agent    │        │ Agent  │              │
│  │Azure Mon. │        │Azure OpenAI│        │GitHub  │              │
│  └───────────┘        └────────────┘        └────────┘              │
│        │                    │                    │                  │
│        └────────────────────┴────────────────────┘                  │
│                             │                                       │
│              ┌──────────────▼──────────────┐                        │
│              │      Orchestrator Agent      │                       │
│              │  TaskPlanner + AgentRegistry │                       │
│              │  Azure MCP Server (8 tools)  │                       │
│              └──────────────────────────────┘                       │
│                             │                                       │
│         ┌───────────────────┴──────────────────┐                    │
│         │                                      │                    │
│  FastAPI + WebSocket                    React 18 Dashboard          │
│  (Azure App Service)                   (Azure Static Web Apps)      │
└─────────────────────────────────────────────────────────────────────┘
```

### State Machine

```
DETECTED → DIAGNOSING → FIXING → DEPLOYING → RESOLVED
                                    └──────→ ROLLED_BACK (on failure)
```

### MCP Execution Plan (7 steps)

```
1. monitor.get_metrics          → Collect current system metrics
2. diagnostic.analyze_incident  → GPT-4o root cause analysis
3. orchestrator.evaluate        → Confidence gate (≥70% → auto-fix)
4. fixer.generate_patch         → Copilot-assisted code fix
5. fixer.validate_fix           → Validate before deploy
6. deploy.execute_deployment    → Azure DevOps deployment
7. monitor.check_health         → Verify resolution
```

---

## 🚀 Deployment

### One-Command Deploy (Windows)

```powershell
# Set Azure OpenAI credentials (optional — works in simulation mode without them)
$env:AZURE_OPENAI_ENDPOINT = "https://your-instance.openai.azure.com/"
$env:AZURE_OPENAI_KEY      = "your-api-key"

# Login and deploy
az login
.\infra\deploy.ps1
```

The script deploys:
- **Azure Container Registry** — stores Docker images
- **Azure App Service Plan** (Linux B1) — hosts the backend
- **Azure App Service** (Linux Container) — FastAPI + WebSocket backend
- **Azure Log Analytics** — centralized logs
- **Application Insights** — APM and metrics

### Output

```
============================================================
  🚀 DEPLOYMENT COMPLETE
  Backend  : https://codeops-sentinel-api.azurewebsites.net
  API Docs : https://codeops-sentinel-api.azurewebsites.net/docs
  Health   : https://codeops-sentinel-api.azurewebsites.net/health
============================================================
```

See [docs/setup.md](docs/setup.md) for full deployment guide including CI/CD setup.

---

## ⚡ Quick Start (Local)

```bash
# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env          # edit with your Azure OpenAI keys (or leave SIMULATION_MODE=true)
uvicorn app.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

- Dashboard: http://localhost:5173
- API Docs:  http://localhost:8000/docs

### Docker Compose

```bash
docker-compose up --build
```

Dashboard: http://localhost:3000

---

## 📡 API Reference

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check (agents + MCP + Azure) |
| `GET` | `/api/incidents` | List all incidents |
| `POST` | `/api/incidents/simulate` | Trigger incident simulation |
| `GET` | `/api/agents/status` | Real-time agent status |
| `GET` | `/api/agents/registry` | Agent capabilities + MCP tools |
| `GET` | `/api/mcp/tools` | All registered MCP tools |
| `POST` | `/api/mcp/call` | Invoke an MCP tool manually |
| `GET` | `/api/mcp/call-log` | Recent MCP call history |
| `WS` | `/ws` | Real-time WebSocket event stream |

---

## 🗂️ Project Structure

```
CodeOps_Sentinel/
├── backend/
│   ├── app/
│   │   ├── agents/        # 4 specialized AI agents + orchestrator
│   │   ├── mcp/           # MCP Server, Tools, Client
│   │   ├── framework/     # AgentRegistry, TaskPlanner, A2AProtocol
│   │   ├── services/      # Azure Monitor, GitHub, AI Foundry
│   │   ├── models/        # Pydantic data models
│   │   └── api/           # FastAPI routes + WebSocket manager
│   ├── Dockerfile
│   ├── startup.sh
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    # React dashboard (Overview, AgentFlow, etc.)
│   │   ├── hooks/         # useWebSocket, useIncidents
│   │   └── utils/         # formatters
│   ├── Dockerfile
│   └── nginx.conf
├── infra/
│   ├── main.bicep         # Azure IaC
│   ├── deploy.ps1         # One-command deploy (Windows)
│   └── deploy.sh          # One-command deploy (Linux/macOS)
├── .github/
│   └── workflows/
│       └── ci-cd.yml      # GitHub Actions pipeline
└── docs/
    └── setup.md           # Full deployment guide
```

---

## ⚙️ Configuration

```bash
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com/
AZURE_OPENAI_KEY=your-key
AZURE_OPENAI_DEPLOYMENT=gpt-4o
SIMULATION_MODE=true        # false to use real Azure OpenAI
GITHUB_TOKEN=ghp_your_token
GITHUB_REPO=your-org/your-repo
```

---

## 🛡️ Built With

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)
![Azure](https://img.shields.io/badge/Azure-0078D4?style=flat&logo=microsoft-azure&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat&logo=github-actions&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=flat&logo=tailwind-css&logoColor=white)

---

Built for the **Microsoft + GitHub AI Hackathon** — leveraging the full Azure AI ecosystem for autonomous DevOps remediation.
