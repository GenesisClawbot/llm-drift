#!/bin/bash
# DriftWatch Backend Startup Script
# Launches llm-drift/backend on port 9001 with required env vars
# Env vars are sourced from environment (set in Railway or locally)
# Run: bash /workspace/llm-drift/start_backend.sh

PORT="${PORT:-9001}"
WORKSPACE="/workspace/llm-drift"

echo "[$(date -u +%H:%M:%S)] Starting DriftWatch backend on port $PORT..."

cd "$WORKSPACE"

exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "$PORT" --log-level warning "$@"
