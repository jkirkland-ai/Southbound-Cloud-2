from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger(__name__)


def send_email(to_addr: str, subject: str, body: str) -> bool:
    """
    Sends via SMTP using env vars:
      SMTP_HOST       (default smtp.gmail.com)
      SMTP_PORT       (default 587)
      SMTP_USER       (username, also used as From if SMTP_FROM unset)
      SMTP_APP_PASSWORD
      SMTP_FROM       (optional)
    Returns True on success, False on misconfiguration or delivery failure.
    """
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_APP_PASSWORD")
    if not user or not password:
        log.warning("SMTP credentials missing; skipping email send")
        return False

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    sender = os.environ.get("SMTP_FROM", user)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_addr
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as e:
        log.error("SMTP send failed: %s", e)
        return False


def format_alert_email(triggers: list[dict], generated_at: str) -> tuple[str, str]:
    subj = f"[crypto-analyzer] {len(triggers)} signal(s) @ {generated_at}"
    lines = [f"Generated at {generated_at} UTC", ""]
    for t in triggers:
        lines.append(f"• [{t['asset']}] {t['rule']} — {t['message']}")
    lines += ["", "— Southbound Cloud Analyzer"]
    return subj, "\n".join(lines)
