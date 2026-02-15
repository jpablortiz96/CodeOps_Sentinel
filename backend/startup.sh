#!/bin/bash
# Azure App Service startup script for CodeOps Sentinel backend
set -e

echo "=== CodeOps Sentinel — Azure App Service Startup ==="
echo "Python: $(python --version)"
echo "Environment: ${APP_ENV:-production}"

# Install/upgrade dependencies (in case image is outdated)
pip install --no-cache-dir -r /app/requirements.txt --quiet

echo "Starting gunicorn with uvicorn workers..."
exec gunicorn app.main:app \
    --workers "${WORKERS:-2}" \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind "0.0.0.0:${PORT:-8000}" \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    --log-level "${LOG_LEVEL:-info}"
