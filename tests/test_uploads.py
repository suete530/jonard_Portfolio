"""Tests para sa uploads.py (Cloudinary, walang totoong upload)."""

import pytest
from flask import Flask

import uploads


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config.update(
        CLOUDINARY_URL="",
        CLOUDINARY_CLOUD_NAME="",
        CLOUDINARY_API_KEY="",
        CLOUDINARY_API_SECRET="",
    )
    return app


def test_disabled_without_config(app):
    with app.app_context():
        assert uploads.is_enabled() is False


def test_enabled_from_url(app):
    app.config["CLOUDINARY_URL"] = "cloudinary://12345:secret@mycloud"
    with app.app_context():
        assert uploads.is_enabled() is True
        assert uploads._settings() == ("mycloud", "12345", "secret")


def test_enabled_from_individual_vars(app):
    app.config.update(CLOUDINARY_CLOUD_NAME="c",
                      CLOUDINARY_API_KEY="k",
                      CLOUDINARY_API_SECRET="s")
    with app.app_context():
        assert uploads._settings() == ("c", "k", "s")


def test_sign_is_deterministic_and_sorted():
    sig = uploads._sign({"timestamp": 1700000000, "public_id": "portfolio/x"},
                        "secret")
    assert sig == uploads._sign(
        {"public_id": "portfolio/x", "timestamp": 1700000000}, "secret")
    assert len(sig) == 40


def test_public_id_from_url_with_version():
    url = ("https://res.cloudinary.com/demo/image/upload/"
           "v1699999999/portfolio/abc123.png")
    assert uploads._public_id_from_url(url) == "portfolio/abc123"


def test_public_id_from_url_without_version():
    url = "https://res.cloudinary.com/demo/image/upload/portfolio/abc123.jpg"
    assert uploads._public_id_from_url(url) == "portfolio/abc123"


def test_is_cloudinary_url():
    assert uploads.is_cloudinary_url(
        "https://res.cloudinary.com/x/image/upload/v1/a.png")
    assert not uploads.is_cloudinary_url("/static/uploads/a.png")
    assert not uploads.is_cloudinary_url(None)


def test_upload_without_config_raises(app):
    with app.app_context():
        with pytest.raises(uploads.UploadError):
            uploads.upload_bytes(b"x", "portfolio/a", "image/png")


def test_upload_success(app, monkeypatch):
    app.config["CLOUDINARY_URL"] = "cloudinary://12345:secret@mycloud"
    captured = {}

    class FakeResp:
        status = 200

        def read(self):
            return (b'{"secure_url": "https://res.cloudinary.com/mycloud/'
                    b'image/upload/v1/portfolio/abc.png"}')

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["data"] = req.data
        return FakeResp()

    monkeypatch.setattr(uploads.urllib.request, "urlopen", fake_urlopen)

    with app.app_context():
        url = uploads.upload_bytes(b"\x89PNG", "portfolio/abc", "image/png")

    assert url.startswith("https://res.cloudinary.com/mycloud/")
    assert "/image/upload" in captured["url"]
    assert b"signature=" in captured["data"]
    assert b"api_key=12345" in captured["data"]
