"""
config.py
---------
Central configuration. Values come from environment variables (.env),
para hindi naka-hardcode ang secrets sa code.
"""

import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # --- Flask core ---
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me-in-production")
    DEBUG = _as_bool(os.environ.get("FLASK_DEBUG"), False)

    # --- Session / cookie security ---
    SESSION_COOKIE_HTTPONLY = True          # JS hindi mababasa ang session cookie
    SESSION_COOKIE_SAMESITE = "Lax"         # panlaban sa CSRF sa cross-site
    SESSION_COOKIE_SECURE = _as_bool(os.environ.get("SESSION_COOKIE_SECURE"), False)
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8   # 8 oras bago mag-expire
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # --- Upload limits (para hindi ma-abuso) ---
    MAX_CONTENT_LENGTH = 4 * 1024 * 1024    # max 4 MB upload
    UPLOAD_FOLDER = os.path.join(basedir, "static", "uploads")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    # --- Database (XAMPP MySQL/MariaDB) ---
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "root")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
    DB_NAME = os.environ.get("DB_NAME", "portfolio_db")
    # Path sa CA cert para sa SSL (kailangan ng managed DB tulad ng Aiven).
    # Blangko = hindi ipipilit ang SSL (ok sa local XAMPP).
    DB_SSL_CA = os.environ.get("DB_SSL_CA", "")
    # Kung 1 at walang DB_SSL_CA: encrypted connection pero hindi bine-verify
    # ang server cert (kailangan ng Aiven/PlanetScale na REQUIRED ang SSL).
    DB_SSL_REQUIRED = _as_bool(os.environ.get("DB_SSL_REQUIRED"), False)

    # --- Security ---
    LOGIN_MAX_ATTEMPTS = 8                  # bago ma-throttle
    LOGIN_WINDOW = "5 minute"               # window ng rate limit

    # Storage ng rate limiter. Sa VPS i-set ang redis://127.0.0.1:6379
    # (shared sa lahat ng gunicorn workers); default = in-memory (dev).
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    # --- Internationalization ---
    LANGUAGES = ["en", "fil", "ceb"]
    BABEL_DEFAULT_LOCALE = "en"
    BABEL_DEFAULT_TIMEZONE = "Asia/Manila"

    # --- Social links (ilagay sa .env; blangko = nakatago ang button) ---
    SOCIAL_LINKS = {
        "facebook": os.environ.get("FACEBOOK_URL", ""),
        "tiktok": os.environ.get("TIKTOK_URL", ""),
    }

    # --- Project categories (para sa filter sa public site) ---
    PROJECT_CATEGORIES = ["webdev", "appdev", "gamedev", "cert"]

    # --- Email (SMTP) para sa contact notifications ---
    # Blangko ang SMTP_USER/PASSWORD = naka-disable ang email sending
    # (naka-save pa rin ang mensahe sa admin inbox).
    SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_TIMEOUT = int(os.environ.get("SMTP_TIMEOUT", "20"))
    MAIL_TO = os.environ.get("MAIL_TO", "")   # email mo (recipient); default = SMTP_USER

    # --- Email via HTTP API (Resend) ---
    # Para sa online host na hinaharang ang SMTP ports (hal. Render free).
    # I-set ang RESEND_API_KEY para gamitin ito imbes na SMTP.
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "Portfolio <onboarding@resend.dev>")

    # --- Cloud image storage (Cloudinary) ---
    # Kapag naka-set, dito naka-save ang image uploads (hindi nawawala sa
    # redeploy). Sinusuportahan ang CLOUDINARY_URL o hiwa-hiwalay na vars.
    CLOUDINARY_URL = os.environ.get("CLOUDINARY_URL", "")
    CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    CLOUDINARY_API_KEY = os.environ.get("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

    # --- AI Assistant (OpenAI-compatible) ---
    # Walang API key = naka-disable ang assistant (hindi lalabas ang error sa user).
    AI_API_KEY = os.environ.get("AI_API_KEY", "")
    AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
    AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "500"))
    AI_TIMEOUT = int(os.environ.get("AI_TIMEOUT", "30"))
    AI_MAX_QUESTION = 500
    AI_MAX_HISTORY = 8

    @classmethod
    def db_config(cls):
        cfg = {
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD,
            "database": cls.DB_NAME,
            "charset": "utf8mb4",
            "autocommit": False,
        }
        if cls.DB_SSL_CA:
            # Managed MySQL (Aiven, etc.) ay nangangailangan ng TLS.
            cfg["ssl_ca"] = cls.DB_SSL_CA
            cfg["ssl_verify_cert"] = True
        elif cls.DB_SSL_REQUIRED:
            # TLS na walang cert verification (kung walang CA file).
            cfg["ssl_disabled"] = False
            cfg["ssl_verify_cert"] = False
        return cfg


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True            # HTTPS-only cookies sa production


def get_config(env=None):
    env = (env or os.environ.get("FLASK_ENV", "development")).lower()
    if env == "production":
        return ProductionConfig
    return Config
