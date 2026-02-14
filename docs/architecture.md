# Architecture — CodeOps Sentinel

## Overview

CodeOps Sentinel is a multi-agent platform where four specialized AI agents collaborate to detect, diagnose, fix, and deploy solutions to production incidents without human intervention.

## Agent Roles

### 1. Monitor Agent
- **Technology**: Azure Monitor, Log Analytics
- **Responsibility**: Continuously polls pipeline status, detects metric anomalies (CPU, memory, error rate, latency)
- **Output**: Structured `Incident` object with metrics snapshot

### 2. Diagnostic Agent
- **Technology**: Azure OpenAI (GPT-4o via Foundry), KQL queries
- **Responsibility**: Performs root cause analysis by correlating logs and metrics
- **Output**: `Diagnosis` with root cause, confidence score, affected services, and recommended action

### 3. Fixer Agent
- **Technology**: GitHub Copilot Agent Mode, GitHub API
- **Responsibility**: Generates targeted code fixes and creates Pull Requests
- **Output**: `Fix` with original/patched code diff and PR URL

### 4. Deploy Agent
- **Technology**: GitHub Actions, Azure DevOps, Kubernetes
- **Responsibility**: Runs test suites, validates pre-deploy conditions, performs rolling deployment, and rolls back on failure
- **Output**: Deployment result with version, pod count, and health status

## Orchestrator (State Machine)

The `OrchestratorAgent` coordinates all agents through a state machine:

```
DETECTED
    │
    ▼ (MonitorAgent creates incident)
DIAGNOSING
    │
    ▼ (DiagnosticAgent returns Diagnosis)
FIXING
    │
    ▼ (FixerAgent creates PR)
DEPLOYING
    │
    ├──▶ RESOLVED     (deploy success)
    └──▶ ROLLED_BACK  (tests fail / health check fails)
```

Every state transition is broadcast via WebSocket to all connected frontend clients.

## Agent Communication (MCP)

Agents communicate via the **Azure MCP (Model Context Protocol) Server**. Each agent registers tools that other agents can call:

| Agent | Exposed Tools |
|-------|--------------|
| Monitor | `check_metrics`, `get_alerts` |
| Diagnostic | `analyze_logs` |
| Fixer | `search_codebase` |
| Deploy | `check_deployment_health` |

## Data Flow

```
HTTP POST /api/incidents/simulate
         │
         ▼
   Create Incident
         │
         ▼
OrchestratorAgent.handle_incident(incident)   ← runs as BackgroundTask
         │
         ├── MonitorAgent.create_incident()
         ├── DiagnosticAgent.diagnose()
         ├── FixerAgent.generate_fix()
         └── DeployAgent.deploy_fix()
                    │
                    ▼
         WebSocket broadcast → React frontend
```

## Real-Time Updates

The backend uses FastAPI WebSockets. The `ConnectionManager` class maintains all active connections and broadcasts:
- `state_transition` — incident status changes
- `agent_activity` — per-agent action updates
- `error` — pipeline failures

The frontend reconnects automatically on disconnect with a 3-second backoff.

## Simulation Mode

When `SIMULATION_MODE=true` (default), all external API calls are replaced with realistic mock data:
- Azure Monitor returns randomized metric data with realistic anomaly patterns
- Azure OpenAI returns pre-written root cause analysis templates
- GitHub API returns simulated PR numbers and URLs
- Deployments have configurable success/failure rates for demo realism
