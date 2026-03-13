#!/bin/bash
# DriftWatch CF Tunnel Keep-Alive Daemon
# Monitors tunnel health and auto-restarts on failure
# Updates api-config.js + Stripe webhook on each restart
#
# Required env vars:
#   STRIPE_SECRET_KEY   — live Stripe secret key
#   STRIPE_WEBHOOK_ID   — webhook endpoint ID (we_...)
#   GH_TOKEN            — GitHub personal access token

BACKEND_PORT="${BACKEND_PORT:-9001}"
LOG="/tmp/keepalive.log"
CF_BIN="${CF_BIN:-/tmp/cloudflared}"
REPO="${REPO:-/workspace/llm-drift}"
WH_ID="${STRIPE_WEBHOOK_ID:-we_1TAHNg7dVu3KiOEDFQwTIjyY}"

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

start_tunnel() {
  log "Starting new CF tunnel..."
  pkill -f "cloudflared tunnel" 2>/dev/null
  sleep 2
  TUNNEL_LOG="/tmp/cf-tunnel-$(date +%s).log"
  nohup "$CF_BIN" tunnel --url "http://localhost:$BACKEND_PORT" --no-autoupdate > "$TUNNEL_LOG" 2>&1 &
  TUNNEL_PID=$!
  log "Tunnel PID: $TUNNEL_PID"

  # Wait for URL
  URL=""
  for i in $(seq 1 20); do
    sleep 3
    URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" | grep -v "^https://api\." | head -1)
    [ -n "$URL" ] && break
  done

  if [ -z "$URL" ]; then
    log "ERROR: Failed to get tunnel URL after 60s"
    return 1
  fi

  log "Tunnel URL: $URL"
  echo "$URL" > /tmp/current-tunnel-url

  # Wait for tunnel to accept connections
  for i in $(seq 1 10); do
    sleep 3
    STATUS=$(curl -s --max-time 5 "$URL/health" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
    if [ "$STATUS" = "ok" ]; then
      log "Tunnel responding: $URL"
      update_configs "$URL"
      return 0
    fi
  done

  log "ERROR: Tunnel not responding after 30s"
  return 1
}

update_configs() {
  local URL="$1"
  log "Updating api-config.js and Stripe webhook to: $URL"

  # Update api-config.js
  cd "$REPO" || return 1
  git pull --rebase origin main 2>/dev/null
  printf "// DriftWatch API URL config\nwindow._DRIFTWATCH_API_URL = '%s';\n" "$URL" > api-config.js
  git add api-config.js
  git commit -m "chore: auto-update CF tunnel URL" 2>/dev/null
  git push origin main 2>&1 | tail -1 >> "$LOG"

  # Update Stripe webhook (if key provided)
  if [ -n "$STRIPE_SECRET_KEY" ] && [ -n "$WH_ID" ]; then
    curl -s -X POST "https://api.stripe.com/v1/webhook_endpoints/$WH_ID" \
      -u "$STRIPE_SECRET_KEY:" \
      -d "url=$URL/stripe/webhook" > /dev/null 2>&1
    log "Stripe webhook updated ✅"
  fi
}

log "=== DriftWatch Tunnel Keep-Alive starting ==="
start_tunnel

while true; do
  sleep 60
  CURRENT_URL=$(cat /tmp/current-tunnel-url 2>/dev/null)
  if [ -z "$CURRENT_URL" ]; then
    log "No tunnel URL — restarting"
    start_tunnel
    continue
  fi
  STATUS=$(curl -s --max-time 8 "$CURRENT_URL/health" | python3 -c "import json,sys; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
  if [ "$STATUS" != "ok" ]; then
    log "Tunnel DOWN — restarting"
    start_tunnel
  fi
done
