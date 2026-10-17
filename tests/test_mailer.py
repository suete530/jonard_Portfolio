"""Tests para sa mailer.py (fakes SMTP, walang totoong email)."""

import pytest
from flask import Flask

import mailer


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config.update(
        SMTP_HOST="smtp.gmail.com",
        SMTP_PORT=587,
        SMTP_USER="",
        SMTP_PASSWORD="",
        SMTP_TIMEOUT=5,
        MAIL_TO="",
    )
    return app


def test_is_enabled_false_when_not_configured(app):
    with app.app_context():
        assert mailer.is_enabled() is False


def test_is_enabled_true_when_configured(app):
    app.config.update(SMTP_USER="me@gmail.com", SMTP_PASSWORD="secret")
    with app.app_context():
        assert mailer.is_enabled() is True


def test_send_without_config_raises(app):
    with app.app_context():
        with pytest.raises(mailer.MailError):
            mailer.send_contact_notification("Ana", "ana@example.com", "Hi", "body")


def test_send_success_and_headers(app, monkeypatch):
    app.config.update(SMTP_USER="me@gmail.com", SMTP_PASSWORD="secret",
                      MAIL_TO="me@gmail.com")
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ehlo(self):
            pass

        def starttls(self, context=None):
            sent["tls"] = True

        def login(self, user, password):
            sent["login"] = user

        def send_message(self, msg):
            sent["subject"] = msg["Subject"]
            sent["reply_to"] = msg["Reply-To"]
            sent["to"] = msg["To"]
            sent["body"] = msg.get_content()

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)

    with app.app_context():
        assert mailer.send_contact_notification(
            "Ana", "ana@example.com", "Project inquiry", "Kumusta!", ) is True

    assert sent["host"] == "smtp.gmail.com"
    assert sent["port"] == 587
    assert sent["tls"] is True
    assert sent["subject"] == "Project inquiry"
    assert sent["reply_to"] == "ana@example.com"
    assert sent["to"] == "me@gmail.com"
    assert "Kumusta!" in sent["body"]


def test_subject_newlines_are_sanitized(app, monkeypatch):
    app.config.update(SMTP_USER="me@gmail.com", SMTP_PASSWORD="secret",
                      MAIL_TO="me@gmail.com")
    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ehlo(self):
            pass

        def starttls(self, context=None):
            pass

        def login(self, *a):
            pass

        def send_message(self, msg):
            sent["subject"] = msg["Subject"]

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)

    with app.app_context():
        mailer.send_contact_notification(
            "Ana", "ana@example.com", "Hi\r\nBcc: evil@x.com", "body")

    assert "\n" not in sent["subject"]
    assert "\r" not in sent["subject"]


def test_fallback_subject_sanitizes_name(app, monkeypatch):
    """Kapag blangko ang subject, ang pangalan ay dapat i-sanitize din
    (hindi dapat mapasok ang CRLF sa email header)."""
    app.config.update(SMTP_USER="me@gmail.com", SMTP_PASSWORD="secret",
                      MAIL_TO="me@gmail.com")
    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def ehlo(self):
            pass

        def starttls(self, context=None):
            pass

        def login(self, *a):
            pass

        def send_message(self, msg):
            sent["subject"] = msg["Subject"]

    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)

    with app.app_context():
        mailer.send_contact_notification(
            "Ana\r\nBcc: evil@x.com", "ana@example.com", "", "body")

    assert "\n" not in sent["subject"]
    assert "\r" not in sent["subject"]
    assert "Ana" in sent["subject"]
