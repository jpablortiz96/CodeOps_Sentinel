import logging
import time
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings

try:
    from api.routes import router
except Exception as _import_err:
    import logging as _log
    _log.critical(f"FATAL: could not import api.routes: {_import_err}", exc_info=True)
    raise

try:
    from api.websocket import manager
except Exception as _import_err:
    import logging as _log
    _log.critical(f"FATAL: could not import api.websocket: {_import_err}", exc_info=True)
    raise

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


# ─── Request logging middleware ───────────────────────────────────────────────
class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        elapsed = (time.monotonic() - start) * 1000
        if request.url.path not in ("/health", "/favicon.ico"):
            logger.info(json.dumps({
                "method": request.method,
                "path":   request.url.path,
                "status": response.status_code,
                "ms":     round(elapsed, 1),
                "client": request.client.host if request.client else "unknown",
            }))
        return response


# ─── Lifespan ─────────────────────────────────────────────────────────────────
_monitor_stop_event: asyncio.Event | None = None
_monitor_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _monitor_stop_event, _monitor_task

    logger.info(json.dumps({
        "event":      "startup",
        "app":        settings.APP_NAME,
        "version":    "2.0.0",
        "env":        settings.APP_ENV,
        "simulation": settings.SIMULATION_MODE,
    }))

    # Register agents at startup
    try:
        from framework.agent_registry import get_agent_registry
        registry = get_agent_registry()
        for name, desc, caps, tools in [
            ("orchestrator", "Main orchestrator — state machine + task planning",
             ["plan", "route", "escalate"],
             ["monitor.check_health", "diagnostic.analyze", "fixer.generate_patch", "deploy.execute"]),
            ("monitor", "Azure Monitor integration — metrics + health checks",
             ["metrics", "health_check", "alerting"],
             ["monitor.check_health", "monitor.get_metrics"]),
            ("diagnostic", "Azure OpenAI powered root-cause analysis",
             ["rca", "log_analysis", "anomaly_detection"],
             ["diagnostic.analyze_incident", "diagnostic.get_root_cause"]),
            ("fixer", "GitHub Copilot assisted patch generation",
             ["patch_generation", "code_fix", "validation"],
             ["fixer.generate_patch", "fixer.validate_fix"]),
            ("deploy", "Azure DevOps deployment and rollback",
             ["deployment", "rollback", "canary"],
             ["deploy.execute_deployment", "deploy.rollback"]),
        ]:
            registry.register(name=name, description=desc, capabilities=caps, tools=tools)
        logger.info(f"Agent Registry: {len(registry.list_agents())} agents ready")
    except Exception as e:
        logger.warning(f"Agent Registry init skipped: {e}")

    # Initialize MCP Server
    try:
        from mcp.mcp_server import get_mcp_server
        from mcp.mcp_tools import TOOL_REGISTRY
        get_mcp_server()
        logger.info(f"MCP Server ready — {len(TOOL_REGISTRY)} tools")
    except Exception as e:
        logger.warning(f"MCP Server init skipped: {e}")

    # Start demo-app background monitor
    try:
        from agents.monitor_agent import MonitorAgent
        from api.routes import incidents_db, agent_statuses

        _monitor_stop_event = asyncio.Event()
        _monitor_agent = MonitorAgent(agent_statuses["monitor"])
        _monitor_task = asyncio.create_task(
            _monitor_agent.background_poll(
                incidents_db=incidents_db,
                agent_statuses=agent_statuses,
                stop_event=_monitor_stop_event,
            )
        )
        logger.info(
            f"Demo-app monitor started — polling {settings.DEMO_APP_URL} "
            f"every {settings.MONITORING_INTERVAL_SECONDS}s"
        )
    except Exception as e:
        logger.warning(f"Demo-app monitor start skipped: {e}")

    yield

    # Stop background monitor on shutdown
    if _monitor_stop_event:
        _monitor_stop_event.set()
    if _monitor_task and not _monitor_task.done():
        try:
            await asyncio.wait_for(_monitor_task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _monitor_task.cancel()

    logger.info(json.dumps({"event": "shutdown", "app": settings.APP_NAME}))


# ─── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="CodeOps Sentinel API",
    description="Multi-agent auto-remediation — Azure MCP + Agent Framework",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — dev + Azure Static Web Apps + Azure Container Apps
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://codeops-sentinel-app.azurestaticapps.net",
    "https://victorious-bay-075f7300f.2.azurestaticapps.net",
]
if getattr(settings, "FRONTEND_URL", None):
    ALLOWED_ORIGINS.append(settings.FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.(azurestaticapps\.net|azurewebsites\.net|azurecontainerapps\.io)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware)


# ─── Global error handler ─────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error":   "internal_server_error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
            "path":    str(request.url.path),
        },
    )


# Routes are mounted at root — no /api prefix.
# API_URL in the frontend points to the bare backend origin.
app.include_router(router)


# ─── Root ─────────────────────────────────────────────────────────────────────
@app.get("/", tags=["system"])
async def root():
    return {
        "name":    "CodeOps Sentinel API",
        "version": "2.0.0",
        "status":  "running",
        "docs":    "/docs",
        "health":  "/health",
    }


# ─── Debug routes (debug mode only) ───────────────────────────────────────────
@app.get("/debug/routes", tags=["system"])
async def debug_routes():
    if not settings.DEBUG:
        return JSONResponse(status_code=403, content={"error": "only available in debug mode"})
    routes = []
    for route in app.routes:
        if hasattr(route, "methods"):
            routes.append({"path": route.path, "methods": sorted(route.methods), "name": route.name})
        else:
            routes.append({"path": route.path, "name": getattr(route, "name", "")})
    return {"total": len(routes), "routes": sorted(routes, key=lambda r: r["path"])}


# ─── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check():
    checks: dict = {"api": True, "websocket": True}

    try:
        from framework.agent_registry import get_agent_registry
        agents = get_agent_registry().list_agents()
        checks["agent_registry"]    = True
        checks["agents_registered"] = len(agents)
    except Exception:
        checks["agent_registry"] = False

    try:
        from mcp.mcp_tools import TOOL_REGISTRY
        checks["mcp_server"] = True
        checks["mcp_tools"]  = len(TOOL_REGISTRY)
    except Exception:
        checks["mcp_server"] = False

    checks["azure_openai"] = (
        bool(settings.AZURE_OPENAI_KEY) if not settings.SIMULATION_MODE else "simulation"
    )

    overall = all(v for v in checks.values() if isinstance(v, bool))
    return {
        "status":         "healthy" if overall else "degraded",
        "app":            settings.APP_NAME,
        "version":        "2.0.0",
        "env":            settings.APP_ENV,
        "checks":         checks,
        "ws_connections": manager.connection_count,
    }


# ─── WebSocket ────────────────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info(f"WebSocket connected. Total: {manager.connection_count}")

    try:
        await manager.send_personal_message(
            {
                "event_type": "connected",
                "data": {
                    "message":    "Connected to CodeOps Sentinel",
                    "version":    "2.0.0",
                    "simulation": settings.SIMULATION_MODE,
                },
            },
            websocket,
        )
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_personal_message({"event_type": "pong"}, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected. Remaining: {manager.connection_count}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
