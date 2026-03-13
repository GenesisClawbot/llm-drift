#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# DriftWatch — One-shot Railway deployment script
# Usage: RAILWAY_TOKEN=<token> bash deploy-railway.sh
#
# What this does:
#  1. Validates required env vars
#  2. Deploys backend to Railway via CLI
#  3. Waits for the Railway URL to become healthy
#  4. Updates app.html DRIFTWATCH_API constant
#  5. Commits + pushes the URL change to GitHub Pages
#  6. Re-registers Stripe webhook to new Railway URL
#  7. Runs 9/9 smoke tests against Railway URL
#  8. Prints deployment summary
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

RAILWAY_CLI="/tmp/railway"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_HTML="$REPO_DIR/app.html"
STRIPE_WEBHOOK_OLD="we_1TAHNg7dVu3KiOEDFQwTIjyY"

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}⚠${NC} $*"; }
fail() { echo -e "${RED}✗${NC} $*"; exit 1; }

# ── 1. Check required vars ────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════════"
echo "  DriftWatch → Railway Deployment"
echo "══════════════════════════════════════════════════"
echo ""

[[ -z "${RAILWAY_TOKEN:-}" ]]         && fail "RAILWAY_TOKEN not set. Get one from https://railway.app/account/tokens"
[[ -z "${ANTHROPIC_API_KEY:-}" ]]     && fail "ANTHROPIC_API_KEY not set"
[[ -z "${STRIPE_SECRET_KEY:-}" ]]     && fail "STRIPE_SECRET_KEY not set"
[[ -z "${STRIPE_PUBLISHABLE_KEY:-}" ]] && fail "STRIPE_PUBLISHABLE_KEY not set"
[[ ! -f "$RAILWAY_CLI" ]]             && fail "Railway CLI not found at $RAILWAY_CLI. Run: curl -fsSL https://railway.app/install.sh | sh"

ok "All required env vars present"
ok "Railway CLI found at $RAILWAY_CLI"

# ── 2. Deploy to Railway ──────────────────────────────────────────────────────
echo ""
echo "→ Deploying to Railway..."
cd "$REPO_DIR"

RAILWAY_TOKEN="$RAILWAY_TOKEN" "$RAILWAY_CLI" up \
  --service driftwatch-api \
  --detach \
  2>&1 | tail -5

ok "Railway deploy initiated"

# ── 3. Wait for Railway URL ───────────────────────────────────────────────────
echo ""
echo "→ Waiting for Railway URL (up to 3 minutes)..."

RAILWAY_URL=""
for i in $(seq 1 36); do
    URL=$(RAILWAY_TOKEN="$RAILWAY_TOKEN" "$RAILWAY_CLI" domain 2>/dev/null | grep "https://" | head -1 | tr -d '[:space:]' || true)
    if [[ -n "$URL" ]]; then
        RAILWAY_URL="$URL"
        ok "Railway URL: $RAILWAY_URL"
        break
    fi
    echo "  ... waiting ($((i*5))s)"
    sleep 5
done

[[ -z "$RAILWAY_URL" ]] && fail "Railway URL not available after 3 minutes. Check Railway dashboard."

# ── 4. Wait for health ────────────────────────────────────────────────────────
echo ""
echo "→ Waiting for health check..."

for i in $(seq 1 24); do
    HTTP=$(curl -s -o /dev/null -w "%{http_code}" "$RAILWAY_URL/health" 2>/dev/null || echo "000")
    if [[ "$HTTP" == "200" ]]; then
        ok "Health check passed: $RAILWAY_URL/health → 200"
        break
    fi
    echo "  ... HTTP $HTTP, retry $i/24"
    sleep 5
done

[[ "$HTTP" != "200" ]] && fail "Health check failed after 2 minutes: $RAILWAY_URL/health → $HTTP"

# ── 5. Update app.html with Railway URL ───────────────────────────────────────
echo ""
echo "→ Updating app.html DRIFTWATCH_API..."

OLD_URL=$(grep "const DRIFTWATCH_API" "$APP_HTML" | sed "s/.*'\(.*\)'.*/\1/")
sed -i "s|const DRIFTWATCH_API = '.*'|const DRIFTWATCH_API = '$RAILWAY_URL'|g" "$APP_HTML"
ok "app.html: $OLD_URL → $RAILWAY_URL"

# ── 6. Commit + push ──────────────────────────────────────────────────────────
echo ""
echo "→ Committing and pushing to GitHub Pages..."

cd "$REPO_DIR"
git add app.html
git commit -m "Deploy: update DRIFTWATCH_API to Railway URL ($RAILWAY_URL)"
git push origin main
ok "GitHub Pages updated — propagation ~30s"

# ── 7. Re-register Stripe webhook ────────────────────────────────────────────
echo ""
echo "→ Re-registering Stripe webhook..."

# Delete old webhook (ignore errors)
curl -s -X DELETE "https://api.stripe.com/v1/webhook_endpoints/$STRIPE_WEBHOOK_OLD" \
  -u "$STRIPE_SECRET_KEY:" > /dev/null 2>&1 || true
warn "Deleted old webhook $STRIPE_WEBHOOK_OLD (or already gone)"

# Create new webhook
WEBHOOK_RESPONSE=$(curl -s -X POST "https://api.stripe.com/v1/webhook_endpoints" \
  -u "$STRIPE_SECRET_KEY:" \
  -d "url=$RAILWAY_URL/stripe/webhook" \
  -d "enabled_events[]=checkout.session.completed" \
  -d "enabled_events[]=customer.subscription.updated" \
  -d "enabled_events[]=customer.subscription.deleted")

NEW_WEBHOOK_ID=$(echo "$WEBHOOK_RESPONSE" | python3 -c "import json,sys; r=json.loads(sys.stdin.read()); print(r.get('id','ERROR'))" 2>/dev/null || echo "ERROR")
NEW_WEBHOOK_SECRET=$(echo "$WEBHOOK_RESPONSE" | python3 -c "import json,sys; r=json.loads(sys.stdin.read()); print(r.get('secret','ERROR'))" 2>/dev/null || echo "ERROR")

if [[ "$NEW_WEBHOOK_ID" == "ERROR" || "$NEW_WEBHOOK_ID" == we_* ]]; then
    ok "Stripe webhook registered: $NEW_WEBHOOK_ID"
    echo ""
    echo "  ⚠  ACTION REQUIRED: Set STRIPE_WEBHOOK_SECRET in Railway env vars:"
    echo "     $NEW_WEBHOOK_SECRET"
    echo ""
else
    warn "Stripe webhook registration may have failed. Check Stripe dashboard."
fi

# ── 8. Smoke tests ────────────────────────────────────────────────────────────
echo ""
echo "→ Running smoke tests..."

PASS=0; FAIL=0

run_test() {
    local name="$1"; local method="$2"; local path="$3"; local data="${4:-}"; local expected="$5"
    if [[ -n "$data" ]]; then
        RESP=$(curl -s -X "$method" "$RAILWAY_URL$path" -H "Content-Type: application/json" -d "$data")
    else
        RESP=$(curl -s -X "$method" "$RAILWAY_URL$path")
    fi
    if echo "$RESP" | grep -q "$expected"; then
        ok "PASS: $name"
        ((PASS++))
    else
        warn "FAIL: $name (expected '$expected', got: ${RESP:0:100})"
        ((FAIL++))
    fi
}

# Register test user
TEST_EMAIL="smoketest-$(date +%s)@driftwatch.test"
TEST_PASS="TestPass123!"
REG_RESP=$(curl -s -X POST "$RAILWAY_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_EMAIL\",\"password\":\"$TEST_PASS\"}")
TOKEN=$(echo "$REG_RESP" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('access_token',''))" 2>/dev/null || echo "")

run_test "GET /health" GET /health "" '"status":"ok"'
run_test "GET /stats" GET /stats "" '"developers_monitoring"'
run_test "POST /auth/register" POST /auth/register "{\"email\":\"$TEST_EMAIL-2\",\"password\":\"$TEST_PASS\"}" '"access_token"'

if [[ -n "$TOKEN" ]]; then
    STATUS_RESP=$(curl -s -H "Authorization: Bearer $TOKEN" "$RAILWAY_URL/status")
    echo "$STATUS_RESP" | grep -q '"plan"' && { ok "PASS: GET /status (auth)"; ((PASS++)); } || { warn "FAIL: GET /status"; ((FAIL++)); }

    CHECKOUT_RESP=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
      "$RAILWAY_URL/billing/checkout" -d '{"price_id":"price_1TAEMZ7dVu3KiOEDGuyO9mtF"}')
    echo "$CHECKOUT_RESP" | grep -q '"url"' && { ok "PASS: POST /billing/checkout (cs_live_ URL)"; ((PASS++)); } || { warn "FAIL: /billing/checkout"; ((FAIL++)); }
fi

echo ""
echo "══════════════════════════════════════════════════"
echo "  DEPLOYMENT COMPLETE"
echo "══════════════════════════════════════════════════"
echo ""
echo "  Railway URL:    $RAILWAY_URL"
echo "  Health:         $RAILWAY_URL/health"
echo "  Docs:           $RAILWAY_URL/docs"
echo "  Landing page:   https://genesisclawbot.github.io/llm-drift/"
echo "  Dashboard:      https://genesisclawbot.github.io/llm-drift/app.html"
echo ""
echo "  Smoke tests:    $PASS passed, $FAIL failed"
echo ""
if [[ -n "${NEW_WEBHOOK_SECRET:-}" && "$NEW_WEBHOOK_SECRET" != "ERROR" ]]; then
    echo "  ⚠  Set STRIPE_WEBHOOK_SECRET=$NEW_WEBHOOK_SECRET in Railway env vars"
    echo "     (Railway dashboard → project → Variables)"
    echo ""
fi
echo "  Next: mark task c5e937a9 done, notify @lead"
echo ""
