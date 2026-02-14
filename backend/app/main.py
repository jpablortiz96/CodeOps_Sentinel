import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .api.routes import router
from .api.websocket import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]")
    logger.info(f"Simulation mode: {settings.SIMULATION_MODE}")
    yield
    logger.info("Shutting down CodeOps Sentinel...")


app = FastAPI(
    title="CodeOps Sentinel API",
    description="Multi-agent auto-remediation platform for DevOps",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - allow frontend dev server and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.azurestaticapps.net",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "simulation_mode": settings.SIMULATION_MODE,
        "websocket_connections": manager.connection_count,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info(f"WebSocket client connected. Total: {manager.connection_count}")

    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            {
                "event_type": "connected",
                "data": {
                    "message": "Connected to CodeOps Sentinel",
                    "version": settings.APP_VERSION,
                },
            },
            websocket,
        )

        # Keep connection alive, handle ping/pong
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await manager.send_personal_message({"event_type": "pong"}, websocket)
            else:
                # Echo back any other messages (for debugging)
                await manager.send_personal_message(
                    {"event_type": "echo", "data": data}, websocket
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket client disconnected. Remaining: {manager.connection_count}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)
