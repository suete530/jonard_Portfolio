"""Tests para sa admin routes (walang totoong DB; routing + error handling)."""

import os

import pytest
from flask import Flask

import database as db
from blueprints.admin import admin_bp
from blueprints.main import main_bp
from extensions import csrf

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _NoDbSession:
    """DBSession peke na palaging nagbabalik ng None (DB down)."""

    def __init__(self, **overrides):
        self.conn = None

    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


@pytest.fixture(scope="module")
def app():
    app = Flask(
        __name__,
        template_folder=os.path.join(PROJECT_ROOT, "templates"),
        static_folder=os.path.join(PROJECT_ROOT, "static"),
    )
    app.config.update(
        SECRET_KEY="test-secret",
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)
    csrf.init_app(app)
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_client(app, client):
    with client.session_transaction() as sess:
        sess["admin_id"] = 1
        sess["admin_username"] = "admin"
    return client


def test_logout_is_post_only(app):
    rule = next(r for r in app.url_map.iter_rules()
                if r.endpoint == "admin.logout")
    assert "POST" in rule.methods
    assert "GET" not in rule.methods


def test_logout_get_returns_405(client):
    assert client.get("/admin/logout").status_code == 405


def test_logout_post_clears_session(admin_client):
    resp = admin_client.post("/admin/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/login")
    with admin_client.session_transaction() as sess:
        assert "admin_id" not in sess


def test_unauthenticated_dashboard_redirects_to_login(client):
    resp = client.get("/admin/")
    assert resp.status_code == 302
    assert "/admin/login" in resp.headers["Location"]


def test_dashboard_handles_db_down(admin_client, monkeypatch):
    monkeypatch.setattr(db, "DBSession", _NoDbSession)
    resp = admin_client.get("/admin/")
    assert resp.status_code == 200
    assert b"0" in resp.data


def test_project_delete_handles_db_down(admin_client, monkeypatch):
    monkeypatch.setattr(db, "DBSession", _NoDbSession)
    resp = admin_client.post("/admin/projects/1/delete")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/projects")


def test_message_delete_handles_db_down(admin_client, monkeypatch):
    monkeypatch.setattr(db, "DBSession", _NoDbSession)
    resp = admin_client.post("/admin/messages/1/delete")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/admin/messages")
