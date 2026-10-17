"""
blueprints/admin.py
-------------------
Admin panel: login, dashboard, CRUD ng projects, at messages inbox.
Protektado ng login_required + rate limiting sa login.
"""

import os
import re
import uuid
from urllib.parse import urlsplit

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, abort, current_app)
from werkzeug.utils import secure_filename

import database as db
import uploads
from extensions import limiter
from security import login_required, verify_password, current_admin_id, clean

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_PER_PAGE = 10


def _slugify(text):
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", text)[:150] or "project"


def _to_int(value, default=0):
    """Ligtas na int conversion (hindi nag-cracrash sa non-numeric input)."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _safe_next_url(target):
    """I-validate ang 'next' redirect laban sa open-redirect.
    Tinatanggap lang ang local path (hal. /admin/projects); tinatanggihan
    ang protocol-relative (//evil.com), absolute URLs, at backslashes."""
    if not target or "\\" in target:
        return None
    if not target.startswith("/") or target.startswith("//"):
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


def _get_page():
    """Kunin ang page number mula sa query string (default 1)."""
    return max(1, _to_int(request.args.get("page"), 1))


def _paginate(page, per_page, total):
    """Magbalik ng dict para sa pagination UI."""
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_prev": page > 1,
        "has_next": page < pages,
        "prev_num": page - 1,
        "next_num": page + 1,
        "offset": (page - 1) * per_page,
    }


def _delete_uploaded_image(image_url):
    """Burahin ang uploaded file (cloud kapag naka-configure ang Cloudinary,
    kundi lokal sa static/uploads). Ligtas: walang path traversal."""
    if not image_url:
        return

    # Cloud storage (Cloudinary)
    if uploads.is_enabled() and uploads.is_cloudinary_url(image_url):
        try:
            uploads.delete_by_url(image_url)
        except uploads.UploadError as e:
            current_app.logger.warning("Hindi nabura ang cloud image %s: %s",
                                       image_url, e)
        return

    marker = "/static/uploads/"
    if marker not in image_url:
        return
    filename = image_url.split(marker, 1)[1]
    filename = filename.split("?", 1)[0].split("#", 1)[0]
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError as e:
        current_app.logger.warning("Hindi nabura ang image %s: %s", path, e)


def _unique_slug(conn, base, table="projects", exclude_id=None):
    slug, n = base, 1
    while True:
        if exclude_id:
            row = db.fetch_one(conn, f"SELECT id FROM {table} WHERE slug=%s AND id<>%s",
                               (slug, exclude_id))
        else:
            row = db.fetch_one(conn, f"SELECT id FROM {table} WHERE slug=%s", (slug,))
        if row is None:
            return slug
        n += 1
        slug = f"{base}-{n}"


def _save_image(file):
    """I-save ang uploaded image nang ligtas (Cloudinary kung naka-configure,
    kundi lokal na disk). Magbalik ng URL o None."""
    if not file or not file.filename:
        return None
    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        flash("Hindi allowed na image type.", "warning")
        return None
    unique = f"{uuid.uuid4().hex[:12]}.{ext}"
    data = file.read()

    if uploads.is_enabled():
        try:
            return uploads.upload_bytes(data, f"portfolio/{unique}",
                                        file.mimetype)
        except uploads.UploadError as e:
            current_app.logger.warning("Cloudinary upload failed: %s", e)
            flash("Hindi na-upload sa cloud storage; naka-save locally.",
                  "warning")

    path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique)
    with open(path, "wb") as fh:
        fh.write(data)
    return url_for("static", filename=f"uploads/{unique}")


# ---------------- Auth ----------------

@admin_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_admin_id():
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = clean(request.form.get("username"), 50)
        password = request.form.get("password", "")

        with db.DBSession() as conn:
            if conn is None:
                flash("Hindi makakonekta sa database.", "danger")
                return render_template("admin/login.html")
            admin = db.fetch_one(conn, "SELECT * FROM admins WHERE username=%s", (username,))

        # Generic error message (hindi ibinubunyag kung username o password ang mali)
        if admin is None or not verify_password(admin["password_hash"], password):
            flash("Maling username o password.", "danger")
            return render_template("admin/login.html")

        session.clear()
        session.permanent = True
        session["admin_id"] = admin["id"]
        session["admin_username"] = admin["username"]
        flash("Welcome back!", "success")
        next_url = _safe_next_url(request.args.get("next"))
        if next_url:
            return redirect(next_url)
        return redirect(url_for("admin.dashboard"))

    return render_template("admin/login.html")


@admin_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Naka-logout ka na.", "success")
    return redirect(url_for("admin.login"))


# ---------------- Dashboard ----------------

@admin_bp.route("/")
@login_required
def dashboard():
    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return render_template("admin/dashboard.html",
                                   total_projects=0, total_templates=0,
                                   unread=0, total_messages=0)
        total_projects = db.fetch_one(conn, "SELECT COUNT(*) AS c FROM projects")["c"]
        total_templates = db.fetch_one(conn, "SELECT COUNT(*) AS c FROM templates")["c"]
        unread = db.fetch_one(conn, "SELECT COUNT(*) AS c FROM messages WHERE is_read=0")["c"]
        total_messages = db.fetch_one(conn, "SELECT COUNT(*) AS c FROM messages")["c"]
    return render_template("admin/dashboard.html",
                           total_projects=total_projects,
                           total_templates=total_templates,
                           unread=unread,
                           total_messages=total_messages)


# ---------------- Projects CRUD ----------------

@admin_bp.route("/projects")
@login_required
def projects():
    page = _get_page()
    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return render_template("admin/projects.html", projects=[],
                                   pagination=_paginate(1, ADMIN_PER_PAGE, 0))
        total = db.fetch_one(conn, "SELECT COUNT(*) AS c FROM projects")["c"]
        pg = _paginate(page, ADMIN_PER_PAGE, total)
        items = db.fetch_all(
            conn,
            "SELECT * FROM projects ORDER BY sort_order ASC, id DESC "
            "LIMIT %s OFFSET %s",
            (ADMIN_PER_PAGE, pg["offset"]),
        )
    return render_template("admin/projects.html", projects=items, pagination=pg)


@admin_bp.route("/projects/new", methods=["GET", "POST"])
@login_required
def project_new():
    if request.method == "POST":
        return _save_project(None)
    return render_template("admin/project_form.html", project=None)


@admin_bp.route("/projects/<int:project_id>/edit", methods=["GET", "POST"])
@login_required
def project_edit(project_id):
    if request.method == "POST":
        return _save_project(project_id)
    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return redirect(url_for("admin.projects"))
        project = db.fetch_one(conn, "SELECT * FROM projects WHERE id=%s", (project_id,))
    if project is None:
        abort(404)
    return render_template("admin/project_form.html", project=project)


def _save_project(project_id):
    title = clean(request.form.get("title"), 150)
    if len(title) < 2:
        flash("Kailangan ng title.", "danger")
        return redirect(request.url)

    category = clean(request.form.get("category"), 20)
    if category not in current_app.config["PROJECT_CATEGORIES"]:
        category = current_app.config["PROJECT_CATEGORIES"][0]

    data = {
        "title": title,
        "summary": clean(request.form.get("summary"), 300),
        "description": clean(request.form.get("description"), 5000),
        "tech_stack": clean(request.form.get("tech_stack"), 255),
        "live_url": clean(request.form.get("live_url"), 500),
        "repo_url": clean(request.form.get("repo_url"), 500),
        "category": category,
        "is_visible": 1 if request.form.get("is_visible") else 0,
        "sort_order": _to_int(request.form.get("sort_order"), 0),
    }

    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return redirect(url_for("admin.projects"))

        # Image: prioritize uploaded file, else URL field
        image_url = _save_image(request.files.get("image")) or clean(request.form.get("image_url"), 500)

        if project_id:
            current = db.fetch_one(conn, "SELECT * FROM projects WHERE id=%s", (project_id,))
            if current is None:
                abort(404)
            slug = _unique_slug(conn, _slugify(title), exclude_id=project_id)
            new_image = image_url or current["image_url"]
            saved = db.execute_query(
                conn,
                """UPDATE projects SET title=%s, slug=%s, summary=%s, description=%s,
                   tech_stack=%s, image_url=%s, live_url=%s, repo_url=%s,
                   category=%s, is_visible=%s, sort_order=%s WHERE id=%s""",
                (data["title"], slug, data["summary"], data["description"],
                 data["tech_stack"], new_image,
                 data["live_url"], data["repo_url"], data["category"],
                 data["is_visible"], data["sort_order"], project_id),
            )
            if saved is None:
                flash("Hindi na-update ang project. Subukan ulit.", "danger")
                return redirect(url_for("admin.projects"))
            # Burahin ang lumang image kung napalitan ito ng bago
            if image_url and image_url != current["image_url"]:
                _delete_uploaded_image(current["image_url"])
            flash("Na-update ang project.", "success")
        else:
            slug = _unique_slug(conn, _slugify(title))
            saved = db.execute_query(
                conn,
                """INSERT INTO projects
                   (title, slug, summary, description, tech_stack, image_url,
                    live_url, repo_url, category, is_visible, sort_order)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (data["title"], slug, data["summary"], data["description"],
                 data["tech_stack"], image_url, data["live_url"], data["repo_url"],
                 data["category"], data["is_visible"], data["sort_order"]),
            )
            if saved is None:
                flash("Hindi nadagdag ang project. Subukan ulit.", "danger")
                return redirect(url_for("admin.projects"))
            flash("Nadagdag ang project.", "success")

    return redirect(url_for("admin.projects"))


@admin_bp.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def project_delete(project_id):
    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return redirect(url_for("admin.projects"))
        row = db.fetch_one(conn, "SELECT image_url FROM projects WHERE id=%s", (project_id,))
        deleted = db.execute_query(conn, "DELETE FROM projects WHERE id=%s", (project_id,))
    if deleted is None:
        flash("Hindi nabura ang project. Subukan ulit.", "danger")
        return redirect(url_for("admin.projects"))
    if row:
        _delete_uploaded_image(row["image_url"])
    flash("Nabura ang project.", "success")
    return redirect(url_for("admin.projects"))


# ---------------- Templates CRUD ----------------

@admin_bp.route("/templates")
@login_required
def templates():
    page = _get_page()
    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return render_template("admin/templates.html", templates=[],
                                   pagination=_paginate(1, ADMIN_PER_PAGE, 0))
        total = db.fetch_one(conn, "SELECT COUNT(*) AS c FROM templates")["c"]
        pg = _paginate(page, ADMIN_PER_PAGE, total)
        items = db.fetch_all(
            conn,
            "SELECT * FROM templates ORDER BY sort_order ASC, id DESC "
            "LIMIT %s OFFSET %s",
            (ADMIN_PER_PAGE, pg["offset"]),
        )
    return render_template("admin/templates.html", templates=items, pagination=pg)


@admin_bp.route("/templates/new", methods=["GET", "POST"])
@login_required
def template_new():
    if request.method == "POST":
        return _save_template(None)
    return render_template("admin/template_form.html", template=None)


@admin_bp.route("/templates/<int:template_id>/edit", methods=["GET", "POST"])
@login_required
def template_edit(template_id):
    if request.method == "POST":
        return _save_template(template_id)
    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return redirect(url_for("admin.templates"))
        item = db.fetch_one(conn, "SELECT * FROM templates WHERE id=%s", (template_id,))
    if item is None:
        abort(404)
    return render_template("admin/template_form.html", template=item)


def _save_template(template_id):
    title = clean(request.form.get("title"), 150)
    if len(title) < 2:
        flash("Kailangan ng title.", "danger")
        return redirect(request.url)

    data = {
        "title": title,
        "summary": clean(request.form.get("summary"), 300),
        "description": clean(request.form.get("description"), 5000),
        "tech_stack": clean(request.form.get("tech_stack"), 255),
        "price": clean(request.form.get("price"), 50),
        "demo_url": clean(request.form.get("demo_url"), 500),
        "buy_url": clean(request.form.get("buy_url"), 500),
        "is_visible": 1 if request.form.get("is_visible") else 0,
        "sort_order": _to_int(request.form.get("sort_order"), 0),
    }

    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return redirect(url_for("admin.templates"))

        image_url = _save_image(request.files.get("image")) or clean(request.form.get("image_url"), 500)

        if template_id:
            current = db.fetch_one(conn, "SELECT * FROM templates WHERE id=%s", (template_id,))
            if current is None:
                abort(404)
            slug = _unique_slug(conn, _slugify(title), table="templates", exclude_id=template_id)
            new_image = image_url or current["image_url"]
            saved = db.execute_query(
                conn,
                """UPDATE templates SET title=%s, slug=%s, summary=%s, description=%s,
                   tech_stack=%s, price=%s, image_url=%s, demo_url=%s, buy_url=%s,
                   is_visible=%s, sort_order=%s WHERE id=%s""",
                (data["title"], slug, data["summary"], data["description"],
                 data["tech_stack"], data["price"], new_image,
                 data["demo_url"], data["buy_url"], data["is_visible"],
                 data["sort_order"], template_id),
            )
            if saved is None:
                flash("Hindi na-update ang template. Subukan ulit.", "danger")
                return redirect(url_for("admin.templates"))
            # Burahin ang lumang image kung napalitan ito ng bago
            if image_url and image_url != current["image_url"]:
                _delete_uploaded_image(current["image_url"])
            flash("Na-update ang template.", "success")
        else:
            slug = _unique_slug(conn, _slugify(title), table="templates")
            saved = db.execute_query(
                conn,
                """INSERT INTO templates
                   (title, slug, summary, description, tech_stack, price, image_url,
                    demo_url, buy_url, is_visible, sort_order)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (data["title"], slug, data["summary"], data["description"],
                 data["tech_stack"], data["price"], image_url, data["demo_url"],
                 data["buy_url"], data["is_visible"], data["sort_order"]),
            )
            if saved is None:
                flash("Hindi nadagdag ang template. Subukan ulit.", "danger")
                return redirect(url_for("admin.templates"))
            flash("Nadagdag ang template.", "success")

    return redirect(url_for("admin.templates"))


@admin_bp.route("/templates/<int:template_id>/delete", methods=["POST"])
@login_required
def template_delete(template_id):
    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return redirect(url_for("admin.templates"))
        row = db.fetch_one(conn, "SELECT image_url FROM templates WHERE id=%s", (template_id,))
        deleted = db.execute_query(conn, "DELETE FROM templates WHERE id=%s", (template_id,))
    if deleted is None:
        flash("Hindi nabura ang template. Subukan ulit.", "danger")
        return redirect(url_for("admin.templates"))
    if row:
        _delete_uploaded_image(row["image_url"])
    flash("Nabura ang template.", "success")
    return redirect(url_for("admin.templates"))


# ---------------- Messages ----------------

@admin_bp.route("/messages")
@login_required
def messages():
    page = _get_page()
    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return render_template("admin/messages.html", messages=[],
                                   pagination=_paginate(1, ADMIN_PER_PAGE, 0))
        total = db.fetch_one(conn, "SELECT COUNT(*) AS c FROM messages")["c"]
        pg = _paginate(page, ADMIN_PER_PAGE, total)
        items = db.fetch_all(
            conn,
            "SELECT * FROM messages ORDER BY created_at DESC LIMIT %s OFFSET %s",
            (ADMIN_PER_PAGE, pg["offset"]),
        )
    return render_template("admin/messages.html", messages=items, pagination=pg)


@admin_bp.route("/messages/<int:message_id>")
@login_required
def message_detail(message_id):
    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return redirect(url_for("admin.messages"))
        msg = db.fetch_one(conn, "SELECT * FROM messages WHERE id=%s", (message_id,))
        if msg is None:
            abort(404)
        if not msg["is_read"]:
            db.execute_query(conn, "UPDATE messages SET is_read=1 WHERE id=%s", (message_id,))
    return render_template("admin/message_detail.html", message=msg)


@admin_bp.route("/messages/<int:message_id>/delete", methods=["POST"])
@login_required
def message_delete(message_id):
    with db.DBSession() as conn:
        if conn is None:
            flash("Hindi makakonekta sa database.", "danger")
            return redirect(url_for("admin.messages"))
        deleted = db.execute_query(conn, "DELETE FROM messages WHERE id=%s", (message_id,))
    if deleted is None:
        flash("Hindi nabura ang mensahe. Subukan ulit.", "danger")
    else:
        flash("Nabura ang mensahe.", "success")
    return redirect(url_for("admin.messages"))
