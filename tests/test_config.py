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
