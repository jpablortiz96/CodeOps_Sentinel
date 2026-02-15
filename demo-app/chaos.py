"""
CodeOps Sentinel — Chaos Engineering Module
Injects real failures into the demo app so CodeOps Sentinel agents can detect,
diagnose, and auto-remediate them in real time.

Each experiment:
  - Runs in a background thread
  - Auto-cancels after AUTO_TIMEOUT_SECONDS (default 120s) if not stopped manually
  - Logs its activity to stdout so Azure Monitor / Log Analytics can capture it
"""
import time
import threading
import logging
import random

from fastapi import APIRouter

logger = logging.getLogger("chaos")

# ── Shared chaos state (read by app.py middleware + route handlers) ────────────
# All keys ending in _active are boolean flags.
chaos_state = {
    "memory_active":     False,
    "cpu_active":        False,
    "latency_active":    False,
    "error_rate_active": False,
    "db_chaos_active":   False,
    # Internal bookkeeping
    "_memory_data":      [],   # list that grows to simulate a memory leak
    "_threads":          {},   # name → threading.Event (stop signals)
    "_started_at":       {},   # name → epoch timestamp
}

AUTO_TIMEOUT_SECONDS = 120   # All experiments self-terminate after 2 minutes

router = APIRouter(prefix="/chaos", tags=["chaos"])


# ── Helper ─────────────────────────────────────────────────────────────────────

def _stop_experiment(name: str):
    """Signal a named background thread to stop and clear its flag."""
    stop_event = chaos_state["_threads"].get(name)
    if stop_event:
        stop_event.set()
    chaos_state[f"{name}_active"] = False
    chaos_state["_threads"].pop(name, None)
    chaos_state["_started_at"].pop(name, None)
    logger.info(f"[CHAOS] Experiment '{name}' stopped.")


def _start_experiment(name: str, target, args=()):
    """Launch a chaos experiment in a daemon thread with auto-timeout."""
    # If already running, stop it first
    _stop_experiment(name)

    stop_event = threading.Event()
    chaos_state["_threads"][name]  = stop_event
    chaos_state["_started_at"][name] = time.time()
    chaos_state[f"{name}_active"]  = True

    def wrapper():
        logger.warning(f"[CHAOS] Experiment '{name}' STARTED — auto-timeout in {AUTO_TIMEOUT_SECONDS}s")
        target(stop_event, *args)
        # Auto-stop after thread exits (timeout reached or manually stopped)
        chaos_state[f"{name}_active"] = False
        chaos_state["_threads"].pop(name, None)
        chaos_state["_started_at"].pop(name, None)
        logger.warning(f"[CHAOS] Experiment '{name}' ENDED.")

    t = threading.Thread(target=wrapper, daemon=True)
    t.start()


# ── Chaos implementations ──────────────────────────────────────────────────────

def _memory_leak_worker(stop: threading.Event):
    """
    Gradually allocates memory by appending large byte arrays every second.
    After AUTO_TIMEOUT_SECONDS the memory is freed and the experiment stops.
    Target: ~50 MB consumed in 30 seconds (1.67 MB/s).
    """
    chunk_size = 1024 * 1024  # 1 MB per chunk
    chunks_per_second = 1      # 1 MB/s → ~50 MB in 50 s (well within 120 s timeout)
    elapsed = 0
    while not stop.is_set() and elapsed < AUTO_TIMEOUT_SECONDS:
        for _ in range(chunks_per_second):
            chaos_state["_memory_data"].append(b"x" * chunk_size)
        current_mb = len(chaos_state["_memory_data"])
        logger.warning(f"[CHAOS] memory-leak: allocated {current_mb} MB so far")
        stop.wait(timeout=1)
        elapsed += 1

    # Free memory when experiment ends
    freed = len(chaos_state["_memory_data"])
    chaos_state["_memory_data"].clear()
    logger.warning(f"[CHAOS] memory-leak: freed {freed} MB")


def _cpu_spike_worker(stop: threading.Event):
    """
    Runs a tight CPU loop on two threads for AUTO_TIMEOUT_SECONDS seconds.
    Uses prime-number sieve to ensure the workload is pure computation.
    """
    def burn(stop_evt: threading.Event):
        while not stop_evt.is_set():
            # CPU-bound work: primality test
            n = random.randint(100_000, 999_999)
            _ = all(n % i != 0 for i in range(2, int(n**0.5) + 1))

    threads = [threading.Thread(target=burn, args=(stop,), daemon=True) for _ in range(2)]
    for t in threads:
        t.start()

    deadline = time.time() + AUTO_TIMEOUT_SECONDS
    while not stop.is_set() and time.time() < deadline:
        stop.wait(timeout=5)
        logger.warning(f"[CHAOS] cpu-spike: still burning CPU ({deadline - time.time():.0f}s remaining)")

    stop.set()   # Signal sub-threads to stop
    for t in threads:
        t.join(timeout=2)


def _latency_worker(stop: threading.Event):
    """
    The actual latency injection happens in the ObservabilityMiddleware by
    reading chaos_state["latency_active"]. This worker just keeps the flag alive
    until timeout or manual stop.
    """
    deadline = time.time() + AUTO_TIMEOUT_SECONDS
    while not stop.is_set() and time.time() < deadline:
        stop.wait(timeout=10)
        remaining = deadline - time.time()
        if remaining > 0:
            logger.warning(f"[CHAOS] latency: +3-5s delay active ({remaining:.0f}s remaining)")


def _error_rate_worker(stop: threading.Event):
    """
    The 50% error injection happens in route handlers by reading
    chaos_state["error_rate_active"]. This worker just keeps the flag alive.
    """
    deadline = time.time() + AUTO_TIMEOUT_SECONDS
    while not stop.is_set() and time.time() < deadline:
        stop.wait(timeout=10)
        remaining = deadline - time.time()
        if remaining > 0:
            logger.warning(f"[CHAOS] error-rate: 50% /products → 500 ({remaining:.0f}s remaining)")


def _db_chaos_worker(stop: threading.Event):
    """
    The DB connection pool exhaustion simulation happens in /orders route
    handlers by reading chaos_state["db_chaos_active"]. Worker keeps flag alive.
    """
    deadline = time.time() + AUTO_TIMEOUT_SECONDS
    while not stop.is_set() and time.time() < deadline:
        stop.wait(timeout=10)
        remaining = deadline - time.time()
        if remaining > 0:
            logger.warning(f"[CHAOS] db-connection: pool exhausted, /orders → 503 ({remaining:.0f}s remaining)")


# ── API Endpoints ──────────────────────────────────────────────────────────────

@router.post("/memory-leak")
async def start_memory_leak():
    """Activates a gradual memory leak (~1 MB/s). Health check memory_mb will rise."""
    _start_experiment("memory", _memory_leak_worker)
    return {
        "experiment":   "memory-leak",
        "status":       "started",
        "description":  "Allocating ~1 MB/s. Check /health → memory_usage_mb rising.",
        "auto_stop_in": f"{AUTO_TIMEOUT_SECONDS}s",
    }


@router.post("/cpu-spike")
async def start_cpu_spike():
    """Activates a CPU spike using 2 burn threads. CPU % will jump to ~100%."""
    _start_experiment("cpu", _cpu_spike_worker)
    return {
        "experiment":   "cpu-spike",
        "status":       "started",
        "description":  "2 threads running CPU-bound loops. Check /health → cpu_percent rising.",
        "auto_stop_in": f"{AUTO_TIMEOUT_SECONDS}s",
    }


@router.post("/latency")
async def start_latency():
    """Injects 3-5s random latency on every non-chaos request."""
    _start_experiment("latency", _latency_worker)
    return {
        "experiment":   "latency",
        "status":       "started",
        "description":  "Every request will be delayed 3-5s. Check /health → avg_latency_ms rising.",
        "auto_stop_in": f"{AUTO_TIMEOUT_SECONDS}s",
    }


@router.post("/error-rate")
async def start_error_rate():
    """Makes 50% of /products requests return HTTP 500."""
    _start_experiment("error_rate", _error_rate_worker)
    return {
        "experiment":   "error-rate",
        "status":       "started",
        "description":  "50% of GET /products → 500. Check /health → error_rate rising.",
        "auto_stop_in": f"{AUTO_TIMEOUT_SECONDS}s",
    }


@router.post("/db-connection")
async def start_db_chaos():
    """Simulates DB connection pool exhausted. All /orders requests return 503."""
    _start_experiment("db_chaos", _db_chaos_worker)
    return {
        "experiment":   "db-connection",
        "status":       "started",
        "description":  "All /orders endpoints → 503. Check /health → active_chaos.",
        "auto_stop_in": f"{AUTO_TIMEOUT_SECONDS}s",
    }


@router.post("/stop")
async def stop_all():
    """Immediately deactivates ALL active chaos experiments and frees memory."""
    stopped = []
    for name in ("memory", "cpu", "latency", "error_rate", "db_chaos"):
        flag_key = f"{name}_active"
        if chaos_state.get(flag_key):
            _stop_experiment(name)
            stopped.append(name)

    # Ensure memory is freed even if the thread already exited
    if chaos_state["_memory_data"]:
        freed = len(chaos_state["_memory_data"])
        chaos_state["_memory_data"].clear()
        logger.warning(f"[CHAOS] stop-all: force-freed {freed} MB")

    logger.warning(f"[CHAOS] All experiments stopped. Stopped: {stopped}")
    return {
        "status":  "all_stopped",
        "stopped": stopped,
        "message": "All chaos experiments deactivated.",
    }


@router.get("/status")
async def chaos_status():
    """Returns which chaos experiments are currently active and for how long."""
    now = time.time()
    experiments = {}
    for name in ("memory", "cpu", "latency", "error_rate", "db_chaos"):
        flag_key  = f"{name}_active"
        is_active = bool(chaos_state.get(flag_key))
        started   = chaos_state["_started_at"].get(name)
        experiments[name] = {
            "active":      is_active,
            "running_for": f"{now - started:.0f}s" if is_active and started else None,
            "auto_stop_in": (
                f"{max(0, AUTO_TIMEOUT_SECONDS - (now - started)):.0f}s"
                if is_active and started else None
            ),
        }

    any_active = any(e["active"] for e in experiments.values())
    memory_allocated_mb = len(chaos_state["_memory_data"])

    return {
        "any_active":           any_active,
        "experiments":          experiments,
        "memory_allocated_mb":  memory_allocated_mb,
    }
