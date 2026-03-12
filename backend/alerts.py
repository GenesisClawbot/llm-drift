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


def _send_email(to_email: str, subject: str, body_text: str, body_html: str) -> bool:
    """Low-level SMTP send. Reused by all email functions."""
    if not SMTP_PASSWORD:
        logger.debug("SMTP_PASSWORD not set — skipping email")
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"DriftWatch <{SMTP_FROM}>"
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo(); server.starttls()
            server.login(SMTP_FROM, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.warning(f"Email failed to {to_email}: {e}")
        return False


def send_welcome_email(to_email: str) -> bool:
    """Welcome email sent immediately after registration."""
    subject = "Welcome to DriftWatch — your first drift check is ready 🚀"
    APP_URL = "https://genesisclawbot.github.io/llm-drift/app.html"
    body_text = f"""Welcome to DriftWatch!

You're on the free tier — 3 test prompts included, no card required.

Here's how to get your first drift check in under 5 minutes:

  1. Open your dashboard: {APP_URL}
  2. Add a test prompt (paste any prompt you use in production)
  3. Click "Run Baseline" — we record what your LLM outputs today
  4. Come back tomorrow — we'll tell you if anything changed

GPT-5.2 changed behaviour on Feb 10, 2026. If you're using OpenAI, run a check now.

Questions? Reply to this email — we read every one.

— The DriftWatch team
"""
    body_html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#1f2937">
<h2 style="color:#6366f1">Welcome to DriftWatch 🚀</h2>
<p>You're on the <strong>free tier</strong> — 3 test prompts included, no card required.</p>
<h3 style="color:#374151">Get your first drift check in 5 minutes:</h3>
<ol style="line-height:2">
  <li>Open your <a href="{APP_URL}" style="color:#6366f1">dashboard</a></li>
  <li>Add a test prompt (paste any prompt you use in production)</li>
  <li>Click <strong>Run Baseline</strong> — we record what your LLM outputs today</li>
  <li>Come back tomorrow — we'll tell you if anything changed</li>
</ol>
<div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;padding:16px;margin:20px 0">
  <strong>⚡ Timely:</strong> GPT-5.2 changed behaviour on Feb 10, 2026. If you're using OpenAI, run a check now to establish your baseline.
</div>
<a href="{APP_URL}" style="background:#6366f1;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block;margin-top:8px">Open Dashboard →</a>
<hr style="margin-top:32px;border:none;border-top:1px solid #e5e7eb">
<p style="color:#9ca3af;font-size:.8rem">DriftWatch — LLM Behavioural Monitoring<br>Questions? Reply to this email.</p>
</body></html>"""
    return _send_email(to_email, subject, body_text, body_html)


def send_trial_limit_email(to_email: str) -> bool:
    """Nudge email sent when user exhausts all 3 free prompts."""
    subject = "You've used all 3 free prompts — upgrade to keep monitoring"
    APP_URL = "https://genesisclawbot.github.io/llm-drift/app.html"
    STARTER_URL = "https://buy.stripe.com/6oU3cp6oHaBT2jR7BE9ws0k"
    body_text = f"""You've used all 3 of your free DriftWatch prompts.

Here's what you found:

  • You've established baselines for your prompts
  • Hourly automated monitoring is one step away

Upgrade to Starter (£99/month) to unlock:
  ✓ 100 test prompts
  ✓ Hourly automated monitoring (runs while you sleep)
  ✓ Email + Slack alerts the moment drift is detected
  ✓ 90-day history

Upgrade now: {STARTER_URL}

If you caught drift already, you know why this matters.
If you haven't — that's because your LLM hasn't changed yet. It will.

— The DriftWatch team
"""
    body_html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#1f2937">
<h2 style="color:#6366f1">You've used all 3 free prompts</h2>
<p>You've established baselines. Now let DriftWatch watch them for you — automatically.</p>
<h3 style="color:#374151">Upgrade to Starter (£99/month):</h3>
<ul style="line-height:2">
  <li>100 test prompts</li>
  <li>Hourly automated monitoring (runs while you sleep)</li>
  <li>Email + Slack alerts the moment drift is detected</li>
  <li>90-day history</li>
</ul>
<a href="{STARTER_URL}" style="background:#6366f1;color:white;padding:14px 28px;border-radius:6px;text-decoration:none;display:inline-block;font-weight:600;font-size:1.1rem">Upgrade to Starter — £99/mo →</a>
<p style="margin-top:20px;color:#6b7280;font-size:.9rem">Or <a href="{APP_URL}" style="color:#6366f1">open your dashboard</a> to review what you've monitored so far.</p>
<hr style="margin-top:32px;border:none;border-top:1px solid #e5e7eb">
<p style="color:#9ca3af;font-size:.8rem">DriftWatch — LLM Behavioural Monitoring<br>Cancel or manage your subscription anytime from your dashboard.</p>
</body></html>"""
    return _send_email(to_email, subject, body_text, body_html)
