"""APScheduler — runs hourly drift checks for all active subscribers."""
import json
import logging
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .models import SessionLocal, User, Prompt, Baseline, RunResult, AlertLog
from .drift_runner import run_check_for_prompt
from .alerts import send_slack_alert, send_email_alert, build_alert_message

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler = None


def run_drift_check_for_user(user_id: str):
    """Run a full drift check for a single user. Called by the scheduler."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.monitoring_active:
            return

        prompts = db.query(Prompt).filter(
            Prompt.user_id == user_id, Prompt.enabled == True
        ).all()

        if not prompts:
            logger.info(f"No prompts for user {user.email} — skipping check")
            return

        results = []
        for prompt in prompts:
            # Get latest baseline
            baseline = db.query(Baseline).filter(
                Baseline.user_id == user_id,
                Baseline.prompt_id == prompt.id
            ).order_by(Baseline.created_at.desc()).first()

            if not baseline:
                logger.info(f"No baseline for prompt {prompt.name} — skipping")
                continue

            validators = json.loads(prompt.validators or "[]")
            try:
                result = run_check_for_prompt(
                    prompt_text=prompt.prompt_text,
                    model=prompt.model,
                    validators=validators,
                    baseline_response=baseline.response,
                    prompt_id=prompt.id,
                    prompt_name=prompt.name,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Drift check failed for prompt {prompt.name}: {e}")
                results.append({
                    "prompt_id": prompt.id,
                    "prompt_name": prompt.name,
                    "error": str(e),
                    "drift_score": 0.0,
                    "alert_level": "none",
                    "regressions": [],
                })

        if not results:
            return

        # Aggregate
        scores = [r["drift_score"] for r in results if "error" not in r]
        avg_drift = sum(scores) / len(scores) if scores else 0.0
        max_drift = max(scores) if scores else 0.0
        alert_count = sum(1 for r in results if r.get("alert_level") not in ("none", None))

        # Save run result
        run = RunResult(
            user_id=user_id,
            run_at=datetime.utcnow(),
            avg_drift=avg_drift,
            max_drift=max_drift,
            alert_count=alert_count,
            results_json=json.dumps(results),
        )
        db.add(run)
        db.commit()

        logger.info(
            f"Drift check for {user.email}: avg={avg_drift:.3f} max={max_drift:.3f} alerts={alert_count}"
        )

        # Send alert if threshold exceeded
        if alert_count > 0 and max_drift >= 0.3:
            run_data = {
                "avg_drift": avg_drift,
                "max_drift": max_drift,
                "alert_count": alert_count,
                "results": results,
            }
            # Slack alert
            slack_delivered = False
            if user.slack_webhook_url:
                slack_delivered = send_slack_alert(user.slack_webhook_url, user.email, run_data)

            # Email alert (fires if SMTP_PASSWORD env var is set)
            email_delivered = send_email_alert(user.email, run_data)

            delivered = slack_delivered or email_delivered

            alert_log = AlertLog(
                user_id=user_id,
                run_result_id=run.id,
                alert_type="drift",
                message=build_alert_message(run_data, user.email),
                sent_at=datetime.utcnow(),
                delivered=delivered,
            )
            db.add(alert_log)
            db.commit()

    except Exception as e:
        logger.error(f"Scheduler error for user {user_id}: {e}")
    finally:
        db.close()


def run_all_active_users():
    """Run drift checks for all active subscribers. Called hourly."""
    logger.info("Hourly drift check starting...")
    db = SessionLocal()
    try:
        active_users = db.query(User).filter(User.monitoring_active == True).all()
        logger.info(f"Running checks for {len(active_users)} active users")
        for user in active_users:
            try:
                run_drift_check_for_user(user.id)
            except Exception as e:
                logger.error(f"Failed check for user {user.id}: {e}")
    finally:
        db.close()
    logger.info("Hourly drift check complete")


def start_scheduler():
    """Start the background scheduler."""
    global _scheduler
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        run_all_active_users,
        trigger=IntervalTrigger(hours=1),
        id="hourly_drift_check",
        name="Hourly drift check for all active subscribers",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started — running hourly drift checks")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
