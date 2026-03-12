"""Alert engine — sends Slack webhooks and logs alerts."""
import json
import logging
import os
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

SLACK_DEFAULT_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")


def send_slack_alert(webhook_url: str, user_email: str, run_result: dict) -> bool:
    """Send a Slack webhook alert for a drift run. Returns True on success."""
    if not webhook_url:
        return False

    avg_drift = run_result.get("avg_drift", 0)
    max_drift = run_result.get("max_drift", 0)
    alert_count = run_result.get("alert_count", 0)
    results = run_result.get("results", [])

    # Build the alert blocks
    alert_prompts = [r for r in results if r.get("alert_level") not in ("none", None)]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🚨 DriftWatch Alert", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Account:*\n{user_email}"},
                {"type": "mrkdwn", "text": f"*Time:*\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
                {"type": "mrkdwn", "text": f"*Avg Drift:*\n{avg_drift:.3f}"},
                {"type": "mrkdwn", "text": f"*Max Drift:*\n{max_drift:.3f}"},
                {"type": "mrkdwn", "text": f"*Alerts:*\n{alert_count} prompt(s)"},
            ],
        },
    ]

    if alert_prompts:
        details = "\n".join(
            f"• *{r.get('prompt_name', r.get('prompt_id', '?'))}*: "
            f"drift={r.get('drift_score', 0):.3f} [{r.get('alert_level','?').upper()}]"
            + (f"\n  ⚠ Regressions: {', '.join(r['regressions'])}" if r.get("regressions") else "")
            for r in alert_prompts[:10]
        )
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Drifted prompts:*\n{details}"},
        })

    blocks.append({
        "type": "actions",
        "elements": [{
            "type": "button",
            "text": {"type": "plain_text", "text": "View Dashboard →"},
            "url": "https://genesisclawbot.github.io/llm-drift/app.html",
            "style": "primary",
        }],
    })

    try:
        resp = httpx.post(webhook_url, json={"blocks": blocks}, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Slack alert failed: {e}")
        return False


def build_alert_message(run_result: dict, user_email: str) -> str:
    """Build a human-readable alert message for logging."""
    avg = run_result.get("avg_drift", 0)
    max_d = run_result.get("max_drift", 0)
    alerts = run_result.get("alert_count", 0)
    return (
        f"DriftWatch alert for {user_email}: "
        f"avg_drift={avg:.3f} max_drift={max_d:.3f} alerts={alerts}"
    )
