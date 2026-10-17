"""
mailer.py
---------
Email notification gamit ang SMTP (stdlib smtplib) para sa contact form.
Walang third-party dependency (tugma sa style ng project).

Gamitin:
    import mailer
    if mailer.is_enabled():
        mailer.send_contact_notification(name, email, subject, body)
"""

import smtplib
import ssl
from email.message import EmailMessage

from flask import current_app


class MailError(Exception):
    """Hindi naipadala ang email."""


def is_enabled():
    """Naka-configure ba ang SMTP? (kailangan ang user + password)."""
    return bool(current_app.config.get("SMTP_USER")
                and current_app.config.get("SMTP_PASSWORD"))


def _sanitize_header(value):
    """Alisin ang CR/LF para maiwasan ang header injection."""
    return " ".join(str(value or "").splitlines()).strip()


def send_contact_notification(name, email, subject, body):
    """Ipadala ang contact message papunta sa MAIL_TO.

    Nagbabalik ng True kapag naipadala; nagtataas ng MailError kung mabigo.
    """
    cfg = current_app.config
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
    msg.set_content(
        f"Pangalan: {name}\n"
        f"Email: {email}\n"
        f"Subject: {subject or '(walang subject)'}\n\n"
        f"{body}\n"
    )

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
