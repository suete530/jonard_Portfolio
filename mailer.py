"""
mailer.py
---------
Email notification para sa contact form.

Dalawang paraan (pipiliin base sa config):
1. Resend HTTP API (RESEND_API_KEY) -- para sa online host na hinaharang
   ang SMTP ports (hal. Render free).
2. SMTP (SMTP_USER/SMTP_PASSWORD) -- para sa local/XAMPP at VPS.

Walang third-party dependency (stdlib lamang, tugma sa style ng project).

Gamitin:
    import mailer
    if mailer.is_enabled():
        mailer.send_contact_notification(name, email, subject, body)
"""

import json
import smtplib
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage

from flask import current_app


class MailError(Exception):
    """Hindi naipadala ang email."""


def is_enabled():
    """Naka-configure ba ang email? (Resend API key o SMTP user+password)."""
    cfg = current_app.config
    if cfg.get("RESEND_API_KEY"):
        return True
    return bool(cfg.get("SMTP_USER") and cfg.get("SMTP_PASSWORD"))


def _sanitize_header(value):
    """Alisin ang CR/LF para maiwasan ang header injection."""
    return " ".join(str(value or "").splitlines()).strip()


def _body_text(name, email, subject, body):
    return (
        f"Pangalan: {name}\n"
        f"Email: {email}\n"
        f"Subject: {subject or '(walang subject)'}\n\n"
        f"{body}\n"
    )


def send_contact_notification(name, email, subject, body):
    """Ipadala ang contact message papunta sa MAIL_TO.

    Nagbabalik ng True kapag naipadala; nagtataas ng MailError kung mabigo.
    """
    cfg = current_app.config
    if cfg.get("RESEND_API_KEY"):
        return _send_resend(cfg, name, email, subject, body)
    return _send_smtp(cfg, name, email, subject, body)


def _send_resend(cfg, name, email, subject, body):
    api_key = cfg["RESEND_API_KEY"]
    recipient = cfg.get("MAIL_TO")
    if not recipient:
        raise MailError("MAIL_TO hindi naka-configure.")

    payload = {
        "from": cfg.get("MAIL_FROM") or "onboarding@resend.dev",
        "to": [recipient],
        "subject": _sanitize_header(subject) or \
            f"Bagong mensahe mula kay {_sanitize_header(name)}",
        "text": _body_text(name, email, subject, body),
    }
    if email:
        payload["reply_to"] = _sanitize_header(email)

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = int(cfg.get("SMTP_TIMEOUT", 20))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status >= 300:
                raise MailError(f"Resend HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise MailError(f"Resend HTTP {e.code}: {detail}") from e
    except (urllib.error.URLError, OSError) as e:
        raise MailError(str(e)) from e
    return True


def _send_smtp(cfg, name, email, subject, body):
    sender = cfg.get("SMTP_USER")
    if not sender or not cfg.get("SMTP_PASSWORD"):
        raise MailError("SMTP hindi naka-configure.")

    recipient = cfg.get("MAIL_TO") or sender

    msg = EmailMessage()
    msg["Subject"] = _sanitize_header(subject) or \
        f"Bagong mensahe mula kay {_sanitize_header(name)}"
    msg["From"] = sender
    msg["To"] = recipient
    if email:
        msg["Reply-To"] = _sanitize_header(email)
    msg.set_content(_body_text(name, email, subject, body))

    host = cfg.get("SMTP_HOST", "smtp.gmail.com")
    port = int(cfg.get("SMTP_PORT", 587))
    timeout = int(cfg.get("SMTP_TIMEOUT", 20))
    try:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(sender, cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise MailError(str(e)) from e
    return True
