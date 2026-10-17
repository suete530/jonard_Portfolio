"""Tests para sa config (env-driven flags)."""

from config import Config, ProductionConfig, _as_bool, get_config


def test_as_bool_variants():
    assert _as_bool("1") is True
    assert _as_bool("true") is True
    assert _as_bool("on") is True
    assert _as_bool("0") is False
    assert _as_bool("", False) is False
    assert _as_bool(None, True) is True


def test_debug_off_by_default():
    # Walang FLASK_DEBUG sa .env -> dapat naka-off ang debug (hindi nag-le-leak)
    assert Config.DEBUG is False


def test_get_config_production():
    assert get_config("production") is ProductionConfig
    assert get_config("development") is Config


def test_db_config_no_ssl_by_default(monkeypatch):
    monkeypatch.setattr(Config, "DB_SSL_CA", "")
    monkeypatch.setattr(Config, "DB_SSL_REQUIRED", False)
    cfg = Config.db_config()
    assert "ssl_ca" not in cfg
    assert "ssl_disabled" not in cfg
    assert cfg["charset"] == "utf8mb4"


def test_db_config_ssl_ca(monkeypatch):
    monkeypatch.setattr(Config, "DB_SSL_CA", "certs/ca.pem")
    cfg = Config.db_config()
    assert cfg["ssl_ca"] == "certs/ca.pem"
    assert cfg["ssl_verify_cert"] is True


def test_db_config_ssl_required_without_ca(monkeypatch):
    monkeypatch.setattr(Config, "DB_SSL_CA", "")
    monkeypatch.setattr(Config, "DB_SSL_REQUIRED", True)
    cfg = Config.db_config()
    assert cfg["ssl_disabled"] is False
    assert cfg["ssl_verify_cert"] is False
    assert "ssl_ca" not in cfg
