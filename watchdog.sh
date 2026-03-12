#!/bin/bash
# DriftWatch Watchdog — keeps backend + Cloudflare tunnel alive
# Run: nohup bash /workspace/llm-drift/watchdog.sh > /tmp/watchdog-llm.log 2>&1 &
# Env vars (STRIPE_SECRET_KEY etc.) should be set in environment before running

API_PORT="${PORT:-9001}"
CF_LOG="/tmp/cloudflared.log"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

check_api() {
    curl -sf --max-time 3 "http://localhost:$API_PORT/health" > /dev/null 2>&1
}

start_api() {
    log "Starting llm-drift backend on port $API_PORT..."
    cd /workspace/llm-drift
    PORT=$API_PORT python3 -m uvicorn backend.main:app \
        --host 0.0.0.0 --port "$API_PORT" --log-level warning \
        > /tmp/llm-drift-backend.log 2>&1 &
    sleep 5
    check_api && log "Backend started OK" || log "Backend failed — see /tmp/llm-drift-backend.log"
}

start_tunnel() {
    log "Starting Cloudflare tunnel → localhost:$API_PORT..."
    /tmp/cloudflared tunnel --url "http://localhost:$API_PORT" \
        --logfile "$CF_LOG" 2>/dev/null &
    sleep 8
    TUNNEL_URL=$(grep -o 'https://[a-zA-Z0-9\-]*\.trycloudflare\.com' "$CF_LOG" | tail -1)
    [ -n "$TUNNEL_URL" ] && log "Tunnel: $TUNNEL_URL" && echo "$TUNNEL_URL" > /tmp/current_tunnel_url.txt || log "Tunnel failed"
}

log "Watchdog started"

while true; do
    check_api || start_api
    pgrep -f "cloudflared tunnel" > /dev/null 2>&1 || start_tunnel
    sleep 30
done
