"""Alert engine — sends Slack webhooks, email alerts, and logs."""
import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx

logger = logging.getLogger(__name__)

# Email config — set SMTP_FROM, SMTP_PASSWORD (Gmail App Password) to activate
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_FROM = os.environ.get("SMTP_FROM", "clawgenesis@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")  # Gmail App Password


def send_email_alert(to_email: str, run_result: dict) -> bool:
    """Send a drift alert email via SMTP. Returns True on success."""
    if not SMTP_PASSWORD:
        logger.debug("SMTP_PASSWORD not set — skipping email alert")
        return False

    avg_drift = run_result.get("avg_drift", 0)
    max_drift = run_result.get("max_drift", 0)
    alert_count = run_result.get("alert_count", 0)
    results = run_result.get("results", [])
    alert_prompts = [r for r in results if r.get("alert_level") not in ("none", None)]

    prompt_rows = "\n".join(
        f"  • {r.get('prompt_name', 'Prompt')}: drift={r.get('drift_score', 0):.3f} "
        f"[{r.get('alert_level','?').upper()}]"
        + (f" — regressions: {', '.join(r['regressions'])}" if r.get("regressions") else "")
        for r in alert_prompts[:10]
    )
    prompt_html = "".join(
        f"<li><strong>{r.get('prompt_name', 'Prompt')}</strong>: "
        f"drift={r.get('drift_score', 0):.3f} [{r.get('alert_level','?').upper()}]"
        + (f"<br><small>Regressions: {', '.join(r['regressions'])}</small>" if r.get("regressions") else "")
        + "</li>"
        for r in alert_prompts[:10]
    )

    subject = f"🚨 DriftWatch Alert — {alert_count} prompt(s) drifted"

    body_text = f"""DriftWatch Alert
================

Your LLM monitoring detected drift at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}.

  Avg drift: {avg_drift:.3f}
  Max drift: {max_drift:.3f}
  Alerts:    {alert_count} prompt(s)

Drifted prompts:
{prompt_rows if prompt_rows else '  (see dashboard for details)'}

View your dashboard:
https://genesisclawbot.github.io/llm-drift/app.html

--
DriftWatch — LLM Behavioural Monitoring
Unsubscribe or adjust alerts in your dashboard settings.
"""

    body_html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
<h2 style="color:#6366f1">🚨 DriftWatch Alert</h2>
<p>Your LLM monitoring detected drift at <strong>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</strong>.</p>
<table style="border-collapse:collapse;margin-bottom:16px">
<tr><td style="padding:4px 12px 4px 0;color:#6b7280">Avg drift</td><td><strong>{avg_drift:.3f}</strong></td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#6b7280">Max drift</td><td><strong>{max_drift:.3f}</strong></td></tr>
<tr><td style="padding:4px 12px 4px 0;color:#6b7280">Alerts</td><td><strong>{alert_count} prompt(s)</strong></td></tr>
</table>
{'<h3>Drifted prompts:</h3><ul>' + prompt_html + '</ul>' if prompt_html else ''}
<p><a href="https://genesisclawbot.github.io/llm-drift/app.html"
   style="background:#6366f1;color:white;padding:10px 20px;border-radius:6px;
          text-decoration:none;display:inline-block">View Dashboard →</a></p>
<hr style="margin-top:32px;border:none;border-top:1px solid #e5e7eb">
<p style="color:#9ca3af;font-size:.8rem">DriftWatch — LLM Behavioural Monitoring<br>
Adjust alerts in your <a href="https://genesisclawbot.github.io/llm-drift/app.html">dashboard settings</a>.</p>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"DriftWatch <{SMTP_FROM}>"
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_FROM, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        logger.info(f"Email alert sent to {to_email}")
        return True
    except Exception as e:
        logger.warning(f"Email alert failed for {to_email}: {e}")
        return False

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
