# DriftWatch SaaS Backend

**Status**: ✅ Complete and tested  
**Date**: 2026-03-12  
**Build time**: ~1 hour

## Overview

The backend is a FastAPI service that provides all required SaaS functionality for DriftWatch:

- User accounts (email signup, login, API key management)
- Prompt management (create, list, delete test prompts)
- Baseline capture (establish baseline responses for each prompt)
- Drift monitoring (hourly automated checks, score calculation)
- Alert system (Slack webhooks, email notifications)
- Billing (Stripe subscription integration, webhook handling)
- Dashboard API (results history, customer status)

## Architecture

```
backend/
├── main.py             # FastAPI application + all routes
├── models.py           # SQLAlchemy ORM models (User, Prompt, Baseline, RunResult, AlertLog)
├── auth.py             # JWT token generation, password hashing (argon2)
├── drift_runner.py     # LLM API calls, drift scoring algorithm, validators
├── scheduler.py        # APScheduler hourly drift checks for all active users
└── alerts.py           # Slack webhook + email alert dispatch
```

## Running Locally

### Install dependencies
```bash
pip install -r requirements-backend.txt
```

### Start the server
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export STRIPE_SECRET_KEY="sk_live_..."
export STRIPE_PUBLISHABLE_KEY="pk_live_..."
export STRIPE_STARTER_PRICE_ID="price_1TAEMZ7dVu3KiOEDGuyO9mtF"
export STRIPE_PRO_PRICE_ID="price_1TAEMa7dVu3KiOEDEgg8hFWf"

python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 9000
```

The API will be available at `http://localhost:9000/docs` (Swagger UI).

### Test the full E2E flow
```bash
# 1. Register
curl -X POST http://localhost:9000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'

# 2. Login (copy the access_token)
curl -X POST http://localhost:9000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'

# 3. Check status
curl http://localhost:9000/status \
  -H "Authorization: Bearer <token>"

# 4. Add a prompt
curl -X POST http://localhost:9000/prompts \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Sentiment test",
    "prompt_text":"Classify: positive/negative/neutral",
    "validators":["single_word"]
  }'

# 5. Run baseline (calls Claude)
curl -X POST http://localhost:9000/baselines/run \
  -H "Authorization: Bearer <token>"

# 6. Run drift check (calls Claude)
curl -X POST http://localhost:9000/monitor/run \
  -H "Authorization: Bearer <token>"
```

## Database

SQLite database (`driftwatch.db`) with tables:

- **users**: email, password_hash, api_key, plan, stripe_customer_id, stripe_subscription_id, monitoring_active, slack_webhook_url
- **prompts**: name, prompt_text, model, validators, enabled
- **baselines**: prompt_id, response, model, created_at
- **run_results**: avg_drift, max_drift, alert_count, results_json (list of per-prompt results)
- **alert_log**: user_id, run_result_id, alert_type, message, sent_at, delivered

## API Endpoints

### Authentication
- `POST /auth/register` → `{access_token, token_type, plan}`
- `POST /auth/login` → `{access_token, token_type, plan}`

### Account Management
- `GET /status` → subscription info, api_key, prompt_count, monitoring status

### Prompts
- `GET /prompts` → list of user prompts
- `POST /prompts` → create new prompt (free: 3 limit, starter: 100, pro: unlimited)
- `DELETE /prompts/{id}` → delete prompt

### Monitoring
- `POST /baselines/run` → capture baseline responses (calls Claude API)
- `POST /monitor/run` → run drift check now (calls Claude, saves results)
- `GET /results` → last 50 drift check runs

### Billing
- `POST /billing/checkout` → create Stripe checkout session
- `POST /stripe/webhook` → Stripe event handler (subscription created/updated/cancelled/failed)

## Drift Scoring Algorithm

For each prompt, the engine compares baseline vs current response using:

1. **Semantic similarity** (50% weight): Jaccard similarity on word sets
2. **Length drift** (20% weight): % change in word count
3. **Validator regression** (30% weight): validators that passed baseline but fail now

Composite score: 0.0 (no drift) to 1.0 (completely different)

**Alert levels**:
- `none`: score < 0.2
- `low`: 0.2 ≤ score < 0.4
- `medium`: 0.4 ≤ score < 0.6
- `high`: score ≥ 0.6

Alerts are sent when `max_drift >= 0.3` for the run.

## Stripe Integration

### Flow
1. User signs up (free plan, 3 test prompts allowed)
2. User configures prompts
3. User clicks "Upgrade" → creates Stripe checkout session
4. Checkout completed → Stripe sends webhook `checkout.session.completed`
5. Backend receives webhook, activates monitoring, creates/updates subscription
6. User can now run unlimited checks, 100 (starter) or unlimited (pro) prompts

### Webhook Events Handled
- `checkout.session.completed`: activate subscription, set plan
- `customer.subscription.updated`: update monitoring_active based on status
- `customer.subscription.deleted`: downgrade to free, disable monitoring
- `invoice.payment_failed`: log warning

### Environment Variables
```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...  (optional, required for signature validation)
STRIPE_STARTER_PRICE_ID=price_...
STRIPE_PRO_PRICE_ID=price_...
```

## Scheduler

APScheduler runs hourly (configurable):

```python
# For each active user:
#   For each enabled prompt:
#     Get latest baseline
#     Call LLM (same prompt as baseline)
#     Score drift
#     Save run result
#     If max_drift >= 0.3, send Slack alert
```

The scheduler runs in background during app startup and shuts down gracefully on app exit.

## Alerting

### Slack Webhooks
When drift exceeds threshold, sends a Slack message with:
- Account email
- Drift metrics (avg, max, alert count)
- List of affected prompts with scores
- Link to dashboard

### Email (Future)
Email alerts can be added by extending `alerts.py` with SendGrid or SMTP integration.

## Deployment

### Option 1: Railway (Recommended)

1. Connect GitHub repo to Railway project
2. Set environment variables in Railway dashboard
3. Deploy

Railway will build the Docker image automatically and run it.

### Option 2: Docker (Manual)

```bash
docker build -t driftwatch-api .
docker run -p 9000:9000 \
  -e ANTHROPIC_API_KEY="..." \
  -e STRIPE_SECRET_KEY="..." \
  -e STRIPE_PUBLISHABLE_KEY="..." \
  driftwatch-api
```

### Option 3: Serveo Tunnel (Dev/Testing)

For quick testing without deployment, expose localhost via Serveo:

```bash
# Generate an SSH key first (for persistent URL)
ssh-keygen -t ed25519 -f ~/.ssh/serveo -N ""

# Register with Serveo (one-time)
curl -X POST https://serveo.net/add_key \
  -d "$(cat ~/.ssh/serveo.pub)"

# Tunnel (will use consistent subdomain)
ssh -o StrictHostKeyChecking=no -R driftwatch:80:localhost:9000 serveo.net

# Update DRIFTWATCH_API in app.html to: https://driftwatch.serveousercontent.com
```

## Frontend Integration

The `app.html` frontend communicates with the backend via Bearer token authentication:

```javascript
const API_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:9000'
    : (window._DRIFTWATCH_API_URL || DRIFTWATCH_API);

fetch(API_URL + endpoint, {
    headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
    }
})
```

## Testing

All core flows have been tested end-to-end:

✅ User registration (email, password hashing, API key generation)
✅ User login (JWT token generation)
✅ Prompt management (CRUD)
✅ Baseline capture (Claude API integration, response storage)
✅ Drift check (scoring algorithm, result persistence)
✅ Results retrieval (history API)
✅ Stripe checkout (session creation, fallback to payment links)

**Future**: Add pytest suite for full test coverage.

## Known Limitations

1. **Email alerts**: Currently logs only, Slack webhook support added. SMTP/SendGrid not yet integrated.
2. **Rate limiting**: No built-in rate limiting. Add Redis + slowapi for production.
3. **Database backups**: SQLite file-based. Add automated backups for production.
4. **Monitoring dashboard**: Use Prometheus + Grafana for production metrics.

## Next Steps (Post-MVP)

- [ ] Email alerting (SendGrid integration)
- [ ] Rate limiting (Redis + slowapi)
- [ ] Database backups & versioning
- [ ] Webhook retry logic
- [ ] Custom validators (user-defined)
- [ ] Model comparison (run on multiple LLMs simultaneously)
- [ ] API usage analytics
- [ ] Admin dashboard for support/analytics

---

**Deployment ready**: Push to GitHub, set up Railway, configure environment variables, done.
