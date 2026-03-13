"""DriftWatch SaaS — FastAPI backend.

Endpoints:
  POST /auth/register      — sign up
  POST /auth/login         — sign in
  GET  /status             — subscription + API key status
  GET  /prompts            — list prompts
  POST /prompts            — create prompt
  DELETE /prompts/{id}     — delete prompt
  POST /baselines/run      — establish baselines for all prompts
  POST /monitor/run        — run drift check now
  GET  /results            — last 50 run results
  POST /billing/checkout   — create Stripe checkout session
  POST /stripe/webhook     — handle Stripe events
"""

import json
import logging
import os
import sys
import threading
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import stripe
import uvicorn
from fastapi import Body, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from .models import (
    AlertLog,
    Baseline,
    Prompt,
    RunResult,
    SessionLocal,
    User,
    WaitlistEntry,
    create_tables,
    generate_api_key,
)
from .drift_runner import run_baseline_for_prompt, run_check_for_prompt
from .scheduler import start_scheduler, stop_scheduler, run_drift_check_for_user
from .alerts import send_welcome_email, send_trial_limit_email, send_first_drift_nudge_email

# ── Config ────────────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

stripe.api_key = STRIPE_SECRET_KEY

# Stripe price IDs (set via env or use the existing payment link products)
STRIPE_STARTER_PRICE = os.environ.get("STRIPE_STARTER_PRICE_ID", "")
STRIPE_PRO_PRICE = os.environ.get("STRIPE_PRO_PRICE_ID", "")

# Plan price lookup (hardcoded Stripe payment links as fallback)
PLAN_PAYMENT_LINKS = {
    "starter": "https://buy.stripe.com/6oU3cp6oHaBT2jR7BE9ws0k",
    "pro": "https://buy.stripe.com/14A5kxeVd25n4rZe029ws0l",
}

FRONTEND_ORIGIN = os.environ.get(
    "FRONTEND_ORIGIN",
    "https://genesisclawbot.github.io"
)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    logger.info("Database tables created/verified")
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="DriftWatch API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Dependency ────────────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email.lower()).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user = User(
        email=req.email.lower(),
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    logger.info(f"New user registered: {user.email}")
    # Send welcome email in background (non-blocking)
    threading.Thread(target=send_welcome_email, args=(user.email,), daemon=True).start()
    return {"access_token": token, "token_type": "bearer", "email": user.email, "plan": user.plan}


@app.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email.lower()).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id, user.email)
    return {"access_token": token, "token_type": "bearer", "email": user.email, "plan": user.plan}


# ── Status ────────────────────────────────────────────────────────────────────

@app.get("/status")
def get_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prompt_count = db.query(Prompt).filter(Prompt.user_id == user.id).count()
    last_run = (
        db.query(RunResult)
        .filter(RunResult.user_id == user.id)
        .order_by(RunResult.run_at.desc())
        .first()
    )
    return {
        "email": user.email,
        "plan": user.plan,
        "monitoring_active": user.monitoring_active,
        "api_key": user.api_key,
        "prompt_count": prompt_count,
        "last_run_at": last_run.run_at.isoformat() + "Z" if last_run else None,
        "stripe_subscription_id": user.stripe_subscription_id,
        "stripe_publishable_key": STRIPE_PUBLISHABLE_KEY,
    }


# ── Prompts ───────────────────────────────────────────────────────────────────

class PromptCreate(BaseModel):
    name: str
    prompt_text: str
    model: Optional[str] = "claude-3-haiku-20240307"
    validators: Optional[list] = []


@app.get("/prompts")
def list_prompts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prompts = db.query(Prompt).filter(Prompt.user_id == user.id).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "prompt_text": p.prompt_text,
            "model": p.model,
            "validators": json.loads(p.validators or "[]"),
            "enabled": p.enabled,
            "created_at": p.created_at.isoformat() + "Z",
        }
        for p in prompts
    ]


@app.post("/prompts", status_code=201)
def create_prompt(
    req: PromptCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Plan limits
    current_count = db.query(Prompt).filter(Prompt.user_id == user.id).count()
    limit = {"free": 3, "starter": 100, "pro": 9999}.get(user.plan, 3)
    if current_count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Prompt limit reached for {user.plan} plan ({limit} max). Upgrade to add more.",
        )

    prompt = Prompt(
        user_id=user.id,
        name=req.name,
        prompt_text=req.prompt_text,
        model=req.model or "claude-3-haiku-20240307",
        validators=json.dumps(req.validators or []),
    )
    db.add(prompt)
    db.commit()
    db.refresh(prompt)

    # If user just hit the free tier limit, send upgrade nudge ONLY if they
    # haven't yet experienced a drift detection (Research Lead finding: firing
    # before the aha moment hurts conversion — the first-drift email converts
    # 5-10x better and should be the primary trigger).
    new_count = current_count + 1
    if user.plan == "free" and new_count >= limit:
        prior_runs = db.query(RunResult).filter(RunResult.user_id == user.id).count()
        if prior_runs == 0:
            # No drift experience yet — gentle limit reminder is appropriate
            threading.Thread(target=send_trial_limit_email, args=(user.email,), daemon=True).start()
        else:
            # They've already run checks — suppress limit email; first-drift nudge
            # will fire (or has fired) at the right moment instead.
            logger.info(f"Suppressed trial_limit_email for {user.email}: {prior_runs} prior runs")

    return {"id": prompt.id, "name": prompt.name, "created": True}


@app.delete("/prompts/{prompt_id}", status_code=204)
def delete_prompt(
    prompt_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prompt = db.query(Prompt).filter(
        Prompt.id == prompt_id, Prompt.user_id == user.id
    ).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db.delete(prompt)
    db.commit()


# ── Baselines ─────────────────────────────────────────────────────────────────

@app.post("/baselines/run")
def run_baselines(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prompts = db.query(Prompt).filter(
        Prompt.user_id == user.id, Prompt.enabled == True
    ).all()
    if not prompts:
        raise HTTPException(status_code=400, detail="No prompts configured. Add prompts first.")

    created = 0
    errors = []
    for prompt in prompts:
        validators = json.loads(prompt.validators or "[]")
        try:
            result = run_baseline_for_prompt(prompt.prompt_text, prompt.model, validators)
        except ValueError as e:
            msg = str(e)
            if "LLM_AUTH_ERROR" in msg:
                raise HTTPException(
                    status_code=503,
                    detail="LLM API key is not configured. Please contact support or try again later."
                )
            errors.append({"prompt": prompt.name, "error": msg})
            continue
        baseline = Baseline(
            user_id=user.id,
            prompt_id=prompt.id,
            response=result["response"],
            model=prompt.model,
        )
        db.add(baseline)
        created += 1

    if created == 0 and errors:
        raise HTTPException(status_code=503, detail=f"Could not reach LLM: {errors[0]['error'][:100]}")

    db.commit()
    logger.info(f"Baselines set for {user.email}: {created} prompts")
    return {"baselines_created": created, "message": f"Baseline captured for {created} prompt(s)", "errors": errors}


# ── Monitor ───────────────────────────────────────────────────────────────────

@app.post("/monitor/run")
def run_monitor(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prompts = db.query(Prompt).filter(
        Prompt.user_id == user.id, Prompt.enabled == True
    ).all()
    if not prompts:
        raise HTTPException(status_code=400, detail="No prompts configured.")

    results = []
    for prompt in prompts:
        baseline = (
            db.query(Baseline)
            .filter(Baseline.user_id == user.id, Baseline.prompt_id == prompt.id)
            .order_by(Baseline.created_at.desc())
            .first()
        )
        if not baseline:
            results.append({
                "prompt_id": prompt.id,
                "prompt_name": prompt.name,
                "error": "No baseline — run baselines first",
                "drift_score": 0.0,
                "alert_level": "none",
                "regressions": [],
            })
            continue

        validators = json.loads(prompt.validators or "[]")
        try:
            r = run_check_for_prompt(
                prompt_text=prompt.prompt_text,
                model=prompt.model,
                validators=validators,
                baseline_response=baseline.response,
                prompt_id=prompt.id,
                prompt_name=prompt.name,
            )
            results.append(r)
        except Exception as e:
            results.append({
                "prompt_id": prompt.id,
                "prompt_name": prompt.name,
                "error": str(e),
                "drift_score": 0.0,
                "alert_level": "none",
                "regressions": [],
            })

    # Aggregate
    scores = [r["drift_score"] for r in results if "error" not in r]
    avg_drift = round(sum(scores) / len(scores), 3) if scores else 0.0
    max_drift = round(max(scores), 3) if scores else 0.0
    alert_count = sum(1 for r in results if r.get("alert_level") not in ("none", None))

    # Persist
    run = RunResult(
        user_id=user.id,
        avg_drift=avg_drift,
        max_drift=max_drift,
        alert_count=alert_count,
        results_json=json.dumps(results),
    )
    db.add(run)
    db.commit()

    logger.info(f"Manual drift check for {user.email}: avg={avg_drift} max={max_drift} alerts={alert_count}")

    # First-drift conversion nudge: fires when a FREE user sees drift for the first time.
    # This is the "aha moment" — the model actually changed on their prompt.
    # Converts 5-10x better than nudging at the prompt-count limit.
    if alert_count > 0 and max_drift >= 0.3 and user.plan == "free":
        prior_drifts = db.query(AlertLog).filter(
            AlertLog.user_id == user.id,
            AlertLog.alert_type == "drift",
        ).count()
        if prior_drifts == 0:
            run_data = {"avg_drift": avg_drift, "max_drift": max_drift,
                        "alert_count": alert_count, "results": results}
            threading.Thread(
                target=send_first_drift_nudge_email,
                args=(user.email, run_data),
                daemon=True,
            ).start()
            # Log it so we don't re-send
            db.add(AlertLog(
                user_id=user.id,
                run_result_id=run.id,
                alert_type="drift",
                message=f"First-drift nudge sent to {user.email}: max={max_drift:.3f}",
                sent_at=datetime.utcnow(),
                delivered=True,
            ))
            db.commit()

    return {
        "run_id": run.id,
        "avg_drift": avg_drift,
        "max_drift": max_drift,
        "alert_count": alert_count,
        "results": results,
    }


# ── Results ───────────────────────────────────────────────────────────────────

@app.get("/results")
def get_results(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    runs = (
        db.query(RunResult)
        .filter(RunResult.user_id == user.id)
        .order_by(RunResult.run_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "run_at": r.run_at.isoformat() + "Z",
            "avg_drift": r.avg_drift,
            "max_drift": r.max_drift,
            "alert_count": r.alert_count,
            "results": json.loads(r.results_json or "[]"),
        }
        for r in runs
    ]


# ── Billing ───────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str  # starter | pro


@app.post("/billing/checkout")
def create_checkout(
    req: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if req.plan not in ("starter", "pro"):
        raise HTTPException(status_code=400, detail="Invalid plan. Choose starter or pro.")

    # If no Stripe Price ID configured, return the static payment link
    price_id = STRIPE_STARTER_PRICE if req.plan == "starter" else STRIPE_PRO_PRICE
    if not price_id:
        return {"checkout_url": PLAN_PAYMENT_LINKS[req.plan]}

    # Create Stripe checkout session
    try:
        # Ensure customer exists
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(email=user.email)
            user.stripe_customer_id = customer.id
            db.commit()

        session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url="https://genesisclawbot.github.io/llm-drift/app.html?checkout=success",
            cancel_url="https://genesisclawbot.github.io/llm-drift/app.html?checkout=cancelled",
            metadata={"user_id": user.id, "plan": req.plan},
        )
        return {"checkout_url": session.url}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout error: {e}")
        # Fallback to payment link
        return {"checkout_url": PLAN_PAYMENT_LINKS[req.plan]}


# ── Stripe Webhooks ───────────────────────────────────────────────────────────

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except Exception as e:
            logger.warning(f"Stripe webhook signature failed: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        # No webhook secret configured — parse raw payload (dev mode)
        try:
            event = json.loads(payload)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload")

    event_type = event.get("type", event.get("event", ""))
    logger.info(f"Stripe event: {event_type}")

    data_obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data_obj, db)
    elif event_type in ("customer.subscription.updated",):
        _handle_subscription_updated(data_obj, db)
    elif event_type in ("customer.subscription.deleted",):
        _handle_subscription_deleted(data_obj, db)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data_obj, db)

    return {"received": True}


def _handle_checkout_completed(session_obj: dict, db: Session):
    """Activate monitoring when customer completes checkout."""
    customer_id = session_obj.get("customer")
    subscription_id = session_obj.get("subscription")
    metadata = session_obj.get("metadata", {})
    user_id = metadata.get("user_id")
    plan = metadata.get("plan", "starter")

    user = None
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
    if not user and customer_id:
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()

    if user:
        user.plan = plan
        user.stripe_subscription_id = subscription_id
        user.monitoring_active = True
        db.commit()
        logger.info(f"Subscription activated for {user.email} — plan={plan}")
    else:
        logger.warning(f"Checkout completed but user not found: customer={customer_id}")


def _handle_subscription_updated(sub_obj: dict, db: Session):
    customer_id = sub_obj.get("customer")
    status = sub_obj.get("status")
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        user.monitoring_active = status in ("active", "trialing")
        db.commit()
        logger.info(f"Subscription updated for {user.email}: status={status}")


def _handle_subscription_deleted(sub_obj: dict, db: Session):
    customer_id = sub_obj.get("customer")
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        user.plan = "free"
        user.monitoring_active = False
        user.stripe_subscription_id = None
        db.commit()
        logger.info(f"Subscription cancelled for {user.email}")


def _handle_payment_failed(invoice_obj: dict, db: Session):
    customer_id = invoice_obj.get("customer")
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user:
        logger.warning(f"Payment failed for {user.email} — monitoring continues for now")


# ── Settings ─────────────────────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    slack_webhook_url: Optional[str] = None


@app.patch("/settings")
def update_settings(
    req: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user notification settings (Slack webhook, etc.)."""
    if req.slack_webhook_url is not None:
        # Basic validation
        if req.slack_webhook_url and not req.slack_webhook_url.startswith("https://hooks.slack.com/"):
            raise HTTPException(status_code=400, detail="Invalid Slack webhook URL")
        user.slack_webhook_url = req.slack_webhook_url or None
    user = db.merge(user)
    db.commit()
    db.refresh(user)
    return {
        "updated": True,
        "slack_webhook_url": user.slack_webhook_url,
    }


@app.get("/settings")
def get_settings(user: User = Depends(get_current_user)):
    """Return current user notification settings."""
    return {
        "slack_webhook_url": user.slack_webhook_url,
        "monitoring_active": user.monitoring_active,
    }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "driftwatch-api", "version": "1.0.0"}


@app.post("/waitlist")
def join_waitlist(payload: dict = Body(...), db: Session = Depends(get_db)):
    """Capture email for PH pre-launch waitlist. No auth required."""
    email = (payload.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    existing = db.query(WaitlistEntry).filter(WaitlistEntry.email == email).first()
    if existing:
        return {"status": "already_subscribed", "email": email}
    entry = WaitlistEntry(email=email, source=payload.get("source", "launch_page"))
    db.add(entry)
    db.commit()
    return {"status": "subscribed", "email": email}


@app.get("/stats")
def public_stats(db: Session = Depends(get_db)):
    """Public stats for social proof widget on landing page. Real counts only."""
    user_count = db.query(User).count()
    paid_count = db.query(User).filter(User.plan != "free").count()
    prompt_count = db.query(Prompt).count()
    return {
        "developers_monitoring": user_count,
        "prompts_watched": prompt_count,
        "paid_subscribers": paid_count,
        "status": "beta",
    }


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 9000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=False)
