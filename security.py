"""
security.py
-----------
Mga helper para sa seguridad:
- Password hashing (PBKDF2-SHA256 via Werkzeug) -- HINDI plaintext.
- login_required decorator para sa admin routes.
- Basic input validation helpers.
"""

import re
import functools

from flask import session, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash, check_password_hash

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------- Password hashing ----------------

def hash_password(plain_password: str) -> str:
    """Gumawa ng secure hash. Ang salt ay kasama na sa output."""
    return generate_password_hash(plain_password, method="pbkdf2:sha256:600000")


def verify_password(stored_hash: str, plain_password: str) -> bool:
    """Ihambing ang input sa hash nang ligtas (constant-time)."""
    try:
        return check_password_hash(stored_hash, plain_password)
    except Exception:
        return False


# ---------------- Access control ----------------

def login_required(view):
    """I-redirect sa login kung hindi naka-login ang admin."""
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Kailangan mong mag-login.", "warning")
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def current_admin_id():
    return session.get("admin_id")


# ---------------- Validation ----------------

def is_valid_email(value: str) -> bool:
    return bool(value) and bool(EMAIL_RE.match(value)) and len(value) <= 150


def clean(value, max_len=500):
    """Trim at limitahan ang haba ng text input."""
    if value is None:
        return ""
    return str(value).strip()[:max_len]
