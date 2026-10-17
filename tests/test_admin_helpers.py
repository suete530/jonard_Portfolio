"""Tests para sa admin.py helper functions (walang DB/app na kailangan)."""

from blueprints.admin import _slugify, _to_int, _safe_next_url, _paginate


# ---------------- _slugify ----------------

def test_slugify_basic():
    assert _slugify("Hello World!") == "hello-world"


def test_slugify_collapses_spaces_and_dashes():
    assert _slugify("My   Cool -- Project") == "my-cool-project"


def test_slugify_empty_uses_fallback():
    assert _slugify("!!!") == "project"


def test_slugify_limits_length():
    assert len(_slugify("a" * 400)) <= 150


# ---------------- _to_int ----------------

def test_to_int_valid():
    assert _to_int("42") == 42
    assert _to_int("  7 ") == 7


def test_to_int_invalid_uses_default():
    assert _to_int("abc", 5) == 5
    assert _to_int(None, 3) == 3
    assert _to_int("", 0) == 0


def test_to_int_default_is_zero():
    assert _to_int("not-a-number") == 0


# ---------------- _safe_next_url (open-redirect protection) ----------------

def test_safe_next_accepts_local_path():
    assert _safe_next_url("/admin/projects") == "/admin/projects"
    assert _safe_next_url("/admin/messages/5") == "/admin/messages/5"


def test_safe_next_rejects_protocol_relative():
    assert _safe_next_url("//evil.com") is None


def test_safe_next_rejects_absolute_urls():
    assert _safe_next_url("http://evil.com") is None
    assert _safe_next_url("https://evil.com/x") is None


def test_safe_next_rejects_backslash():
    assert _safe_next_url("/\\evil.com") is None


def test_safe_next_rejects_scheme_only():
    assert _safe_next_url("javascript:alert(1)") is None


def test_safe_next_rejects_empty():
    assert _safe_next_url(None) is None
    assert _safe_next_url("") is None


# ---------------- _paginate ----------------

def test_paginate_empty():
    pg = _paginate(1, 10, 0)
    assert pg["pages"] == 1
    assert pg["page"] == 1
    assert pg["has_prev"] is False
    assert pg["has_next"] is False


def test_paginate_first_page():
    pg = _paginate(1, 10, 25)
    assert pg["pages"] == 3
    assert pg["offset"] == 0
    assert pg["has_prev"] is False
    assert pg["has_next"] is True


def test_paginate_last_page():
    pg = _paginate(3, 10, 25)
    assert pg["page"] == 3
    assert pg["offset"] == 20
    assert pg["has_next"] is False


def test_paginate_clamps_out_of_range():
    pg = _paginate(99, 10, 25)
    assert pg["page"] == 3
    assert pg["has_next"] is False
