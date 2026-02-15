# ShopDemo API — CodeOps Sentinel Demo Target

A realistic e-commerce API designed to be monitored and auto-repaired by CodeOps Sentinel.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | App status + active chaos summary |
| GET | `/health` | Full health metrics (memory, CPU, error rate, latency) |
| GET | `/products` | List 10 products (supports `?category=Electronics`) |
| GET | `/products/{id}` | Product detail |
| POST | `/orders` | Create order (validates stock) |
| GET | `/orders` | List orders |
| GET | `/metrics` | Prometheus-style text metrics |

## Chaos Endpoints

| Method | Path | What it breaks |
|--------|------|----------------|
| POST | `/chaos/memory-leak` | Allocates ~1 MB/s — memory_usage_mb rises in `/health` |
| POST | `/chaos/cpu-spike` | 2 burn threads — cpu_percent spikes in `/health` |
| POST | `/chaos/latency` | Adds 3-5s random delay to every request |
| POST | `/chaos/error-rate` | 50% of `/products` requests return HTTP 500 |
| POST | `/chaos/db-connection` | All `/orders` requests return HTTP 503 |
| POST | `/chaos/stop` | Stops ALL active experiments immediately |
| GET | `/chaos/status` | Shows which experiments are running |

All chaos experiments **auto-stop after 120 seconds** if not stopped manually.

## Running Locally

```bash
cd demo-app
pip install -r requirements.txt
uvicorn app:app --port 8080 --reload
```

Swagger UI: http://localhost:8080/docs

## Running with Docker

```bash
docker build -t shopdemo .
docker run -p 8080:8080 shopdemo
```

## Deploy to Azure (ACR Tasks)

```powershell
az acr build `
    --registry codeopssentinelacr `
    --resource-group CodeOpsSentinel-rg `
    --image "shopdemo:latest" `
    ".\demo-app"

az containerapp create `
    --name shopdemo `
    --resource-group CodeOpsSentinel-rg `
    --environment codeops-sentinel-env `
    --image "codeopssentinelacr.azurecr.io/shopdemo:latest" `
    --registry-server codeopssentinelacr.azurecr.io `
    --target-port 8080 `
    --ingress external `
    --min-replicas 1 --max-replicas 1 `
    --cpu 0.5 --memory 1.0Gi
```

## How CodeOps Sentinel Uses This App

1. **Configure** CodeOps Sentinel to monitor `https://<shopdemo-url>/health`
2. **Trigger** a chaos experiment via any `/chaos/*` endpoint
3. **Watch** CodeOps Sentinel detect the anomaly (memory, CPU, error rate, or latency spike)
4. **Observe** the multi-agent pipeline: Monitor → Diagnostic → Fixer → Deploy
5. **Verify** the app returns to `healthy` status after remediation

## Health Status Logic

| Condition | Status |
|-----------|--------|
| memory > 400 MB OR cpu > 85% OR error_rate > 30% OR latency > 2000ms | `critical` |
| any chaos active OR error_rate > 10% OR latency > 500ms | `degraded` |
| otherwise | `healthy` |
