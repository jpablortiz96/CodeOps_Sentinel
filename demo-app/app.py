"""
CodeOps Sentinel — Demo E-Commerce API
A realistic FastAPI app that CodeOps Sentinel monitors and auto-repairs.
Chaos experiments are injected via chaos.py endpoints.
"""
import time
import threading
import logging
from contextlib import asynccontextmanager
from collections import defaultdict
from typing import Dict, List, Optional

import psutil
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from chaos import chaos_state, router as chaos_router

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("demo-app")

# ── App startup time ───────────────────────────────────────────────────────────
START_TIME = time.time()

# ── Internal metrics (thread-safe via lock) ────────────────────────────────────
_metrics_lock = threading.Lock()
_metrics: Dict = {
    "request_count":   0,
    "error_count":     0,
    "latency_sum_ms":  0.0,
    "endpoint_counts": defaultdict(int),
    "endpoint_errors": defaultdict(int),
}

def record_request(path: str, latency_ms: float, is_error: bool):
    with _metrics_lock:
        _metrics["request_count"]      += 1
        _metrics["latency_sum_ms"]     += latency_ms
        _metrics["endpoint_counts"][path] += 1
        if is_error:
            _metrics["error_count"] += 1
            _metrics["endpoint_errors"][path] += 1


# ── Middleware: latency injection + metrics ────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware

class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()

        # Chaos: artificial latency injection
        if chaos_state["latency_active"] and not request.url.path.startswith("/chaos"):
            import asyncio, random
            delay = random.uniform(3.0, 5.0)
            logger.warning(f"[CHAOS] Injecting {delay:.1f}s latency on {request.url.path}")
            await asyncio.sleep(delay)

        try:
            response = await call_next(request)
            elapsed = (time.monotonic() - start) * 1000
            is_error = response.status_code >= 500
            record_request(request.url.path, elapsed, is_error)
            return response
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            record_request(request.url.path, elapsed, is_error=True)
            raise exc


# ── Data models ────────────────────────────────────────────────────────────────
class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float
    stock: int
    sku: str

class OrderItem(BaseModel):
    product_id: int
    quantity: int

class Order(BaseModel):
    id: str
    items: List[OrderItem]
    total: float
    status: str
    created_at: float

class OrderRequest(BaseModel):
    items: List[OrderItem]
    customer_email: str


# ── Seed product catalog ───────────────────────────────────────────────────────
PRODUCTS: Dict[int, Product] = {
    p.id: p for p in [
        Product(id=1,  name="Wireless Headphones Pro",  category="Electronics",   price=149.99, stock=42,  sku="ELEC-001"),
        Product(id=2,  name="Mechanical Keyboard",       category="Electronics",   price=89.99,  stock=28,  sku="ELEC-002"),
        Product(id=3,  name="Standing Desk Mat",          category="Office",        price=49.99,  stock=115, sku="OFFC-001"),
        Product(id=4,  name="USB-C Hub 7-in-1",           category="Electronics",   price=34.99,  stock=76,  sku="ELEC-003"),
        Product(id=5,  name="Ergonomic Mouse",             category="Electronics",   price=59.99,  stock=53,  sku="ELEC-004"),
        Product(id=6,  name="Laptop Stand Adjustable",    category="Office",        price=39.99,  stock=88,  sku="OFFC-002"),
        Product(id=7,  name="Bamboo Desk Organizer",      category="Office",        price=24.99,  stock=200, sku="OFFC-003"),
        Product(id=8,  name="4K Webcam 60fps",             category="Electronics",   price=129.99, stock=19,  sku="ELEC-005"),
        Product(id=9,  name="Noise-Cancelling Earbuds",   category="Electronics",   price=79.99,  stock=61,  sku="ELEC-006"),
        Product(id=10, name="Monitor Light Bar",           category="Electronics",   price=44.99,  stock=34,  sku="ELEC-007"),
    ]
}

# In-memory orders store
_orders: Dict[str, Order] = {}
_orders_lock = threading.Lock()


# ── App lifecycle ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[STARTUP] Demo E-Commerce API starting up")
    logger.info(f"[STARTUP] {len(PRODUCTS)} products loaded, chaos module ready")
    yield
    logger.info("[SHUTDOWN] Demo E-Commerce API shutting down")
    chaos_state["memory_active"]    = False
    chaos_state["cpu_active"]       = False
    chaos_state["latency_active"]   = False
    chaos_state["error_rate_active"] = False
    chaos_state["db_chaos_active"]  = False


app = FastAPI(
    title="ShopDemo API",
    description="Demo e-commerce API monitored by CodeOps Sentinel",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(ObservabilityMiddleware)
app.include_router(chaos_router)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    proc = psutil.Process()
    mem_mb = proc.memory_info().rss / 1_048_576
    uptime = time.time() - START_TIME
    with _metrics_lock:
        req_count = _metrics["request_count"]
        err_count = _metrics["error_count"]

    active_chaos = [k for k, v in chaos_state.items() if k.endswith("_active") and v]
    return {
        "app":         "ShopDemo API",
        "version":     "1.0.0",
        "status":      "degraded" if active_chaos else "healthy",
        "uptime_s":    round(uptime, 1),
        "memory_mb":   round(mem_mb, 1),
        "requests":    req_count,
        "errors":      err_count,
        "active_chaos": active_chaos,
    }


@app.get("/health")
async def health():
    proc     = psutil.Process()
    mem_mb   = proc.memory_info().rss / 1_048_576
    cpu_pct  = psutil.cpu_percent(interval=0.1)
    uptime   = time.time() - START_TIME

    with _metrics_lock:
        req_count  = _metrics["request_count"]
        err_count  = _metrics["error_count"]
        lat_sum    = _metrics["latency_sum_ms"]

    error_rate  = (err_count / req_count * 100) if req_count > 0 else 0.0
    avg_latency = (lat_sum / req_count) if req_count > 0 else 0.0

    active_chaos = [k for k, v in chaos_state.items() if k.endswith("_active") and v]

    # Determine overall status
    if mem_mb > 400 or cpu_pct > 85 or error_rate > 30 or avg_latency > 2000:
        status = "critical"
    elif active_chaos or error_rate > 10 or avg_latency > 500:
        status = "degraded"
    else:
        status = "healthy"

    if status != "healthy":
        logger.warning(
            f"[HEALTH] status={status} mem={mem_mb:.0f}MB cpu={cpu_pct:.0f}% "
            f"error_rate={error_rate:.1f}% latency={avg_latency:.0f}ms chaos={active_chaos}"
        )

    return {
        "status":          status,
        "memory_usage_mb": round(mem_mb, 1),
        "cpu_percent":     round(cpu_pct, 1),
        "uptime_seconds":  round(uptime, 1),
        "request_count":   req_count,
        "error_rate":      round(error_rate, 2),
        "avg_latency_ms":  round(avg_latency, 1),
        "active_chaos":    active_chaos,
    }


@app.get("/products")
async def list_products(category: Optional[str] = None):
    # Chaos: random 500 errors on /products
    if chaos_state["error_rate_active"]:
        import random
        if random.random() < 0.50:
            logger.error("[CHAOS] error-rate chaos: returning 500 on /products")
            raise HTTPException(status_code=500, detail="Internal Server Error (chaos-injected)")

    products = list(PRODUCTS.values())
    if category:
        products = [p for p in products if p.category.lower() == category.lower()]
    return {"products": products, "total": len(products)}


@app.get("/products/{product_id}")
async def get_product(product_id: int):
    if chaos_state["error_rate_active"]:
        import random
        if random.random() < 0.50:
            logger.error(f"[CHAOS] error-rate chaos: returning 500 on /products/{product_id}")
            raise HTTPException(status_code=500, detail="Internal Server Error (chaos-injected)")

    product = PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return product


@app.post("/orders", status_code=201)
async def create_order(req: OrderRequest):
    # Chaos: simulate DB connection pool exhausted
    if chaos_state["db_chaos_active"]:
        logger.error("[CHAOS] db-connection chaos: returning 503 on /orders")
        raise HTTPException(
            status_code=503,
            detail="Service Unavailable: database connection pool exhausted (chaos-injected)",
        )

    # Validate stock and compute total
    total = 0.0
    validated_items = []
    for item in req.items:
        product = PRODUCTS.get(item.product_id)
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if product.stock < item.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock for '{product.name}': available={product.stock}, requested={item.quantity}",
            )
        total += product.price * item.quantity
        validated_items.append(item)

    # Deduct stock
    for item in validated_items:
        PRODUCTS[item.product_id].stock -= item.quantity

    import uuid
    order = Order(
        id=str(uuid.uuid4())[:8],
        items=validated_items,
        total=round(total, 2),
        status="confirmed",
        created_at=time.time(),
    )
    with _orders_lock:
        _orders[order.id] = order

    logger.info(f"[ORDER] Created order {order.id} total=${order.total:.2f} items={len(order.items)}")
    return order


@app.get("/orders")
async def list_orders():
    if chaos_state["db_chaos_active"]:
        logger.error("[CHAOS] db-connection chaos: returning 503 on /orders")
        raise HTTPException(
            status_code=503,
            detail="Service Unavailable: database connection pool exhausted (chaos-injected)",
        )
    with _orders_lock:
        return {"orders": list(_orders.values()), "total": len(_orders)}


@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """Prometheus-compatible plain-text metrics for scraping."""
    proc    = psutil.Process()
    mem_mb  = proc.memory_info().rss / 1_048_576
    cpu_pct = psutil.cpu_percent(interval=0.1)
    uptime  = time.time() - START_TIME

    with _metrics_lock:
        req_count  = _metrics["request_count"]
        err_count  = _metrics["error_count"]
        lat_sum    = _metrics["latency_sum_ms"]

    avg_latency = (lat_sum / req_count) if req_count > 0 else 0.0
    error_rate  = (err_count / req_count) if req_count > 0 else 0.0

    active_chaos = sum(1 for k, v in chaos_state.items() if k.endswith("_active") and v)

    lines = [
        "# HELP shopdemo_requests_total Total HTTP requests",
        "# TYPE shopdemo_requests_total counter",
        f"shopdemo_requests_total {req_count}",
        "",
        "# HELP shopdemo_errors_total Total HTTP errors (5xx)",
        "# TYPE shopdemo_errors_total counter",
        f"shopdemo_errors_total {err_count}",
        "",
        "# HELP shopdemo_error_rate Current error rate (0-1)",
        "# TYPE shopdemo_error_rate gauge",
        f"shopdemo_error_rate {error_rate:.4f}",
        "",
        "# HELP shopdemo_latency_avg_ms Average request latency in milliseconds",
        "# TYPE shopdemo_latency_avg_ms gauge",
        f"shopdemo_latency_avg_ms {avg_latency:.2f}",
        "",
        "# HELP shopdemo_memory_mb Resident memory usage in megabytes",
        "# TYPE shopdemo_memory_mb gauge",
        f"shopdemo_memory_mb {mem_mb:.1f}",
        "",
        "# HELP shopdemo_cpu_percent CPU utilization percent",
        "# TYPE shopdemo_cpu_percent gauge",
        f"shopdemo_cpu_percent {cpu_pct:.1f}",
        "",
        "# HELP shopdemo_uptime_seconds Process uptime in seconds",
        "# TYPE shopdemo_uptime_seconds counter",
        f"shopdemo_uptime_seconds {uptime:.0f}",
        "",
        "# HELP shopdemo_chaos_active Number of active chaos experiments",
        "# TYPE shopdemo_chaos_active gauge",
        f"shopdemo_chaos_active {active_chaos}",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=False)
