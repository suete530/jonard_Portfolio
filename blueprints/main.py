"""
blueprints/main.py
------------------
Public na pages: Home, Projects, Project detail, Contact.
"""

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort, jsonify, current_app)
from flask_babel import gettext as _

import assistant
import database as db
import mailer
from extensions import limiter
from security import clean, is_valid_email

main_bp = Blueprint("main", __name__)


def _visible_projects(conn, limit=None):
    q = ("SELECT * FROM projects WHERE is_visible=1 "
         "ORDER BY sort_order ASC, created_at DESC")
    if limit:
        q += f" LIMIT {int(limit)}"
    return db.fetch_all(conn, q)


@main_bp.route("/")
def index():
    with db.DBSession() as conn:
        if conn is None:
            return render_template("index.html", projects=[], db_error=True)
        projects = _visible_projects(conn, limit=6)
    return render_template("index.html", projects=projects)


@main_bp.route("/projects")
def projects():
    category = request.args.get("category")
    if category not in current_app.config["PROJECT_CATEGORIES"]:
        category = None
    with db.DBSession() as conn:
        if conn is None:
            return render_template("projects.html", projects=[], db_error=True,
                                   active_category=None)
        if category:
            items = db.fetch_all(
                conn,
                "SELECT * FROM projects WHERE is_visible=1 AND category=%s "
                "ORDER BY sort_order ASC, created_at DESC",
                (category,),
            )
        else:
            items = _visible_projects(conn)
    return render_template("projects.html", projects=items,
                           active_category=category)


@main_bp.route("/projects/<slug>")
def project_detail(slug):
    with db.DBSession() as conn:
        if conn is None:
            abort(404)
        project = db.fetch_one(
            conn,
            "SELECT * FROM projects WHERE slug=%s AND is_visible=1",
            (slug,),
        )
    if project is None:
        abort(404)
    return render_template("project_detail.html", project=project)


@main_bp.route("/templates")
def templates():
    with db.DBSession() as conn:
        if conn is None:
            return render_template("templates.html", templates=[], db_error=True)
        items = db.fetch_all(
            conn,
            "SELECT * FROM templates WHERE is_visible=1 "
            "ORDER BY sort_order ASC, created_at DESC",
        )
    return render_template("templates.html", templates=items)


@main_bp.route("/templates/<slug>")
def template_detail(slug):
    with db.DBSession() as conn:
        if conn is None:
            abort(404)
        item = db.fetch_one(
            conn,
            "SELECT * FROM templates WHERE slug=%s AND is_visible=1",
            (slug,),
        )
    if item is None:
        abort(404)
    return render_template("template_detail.html", template=item)


@main_bp.route("/contact", methods=["GET", "POST"])
@limiter.limit("5 per 10 minute", methods=["POST"])
def contact():
    if request.method == "POST":
        name = clean(request.form.get("name"), 100)
        email = clean(request.form.get("email"), 150)
        subject = clean(request.form.get("subject"), 200)
        body = clean(request.form.get("body"), 5000)

        errors = []
        if len(name) < 2:
            errors.append(_("Please enter your name."))
        if not is_valid_email(email):
            errors.append(_("A valid email is required."))
        if len(body) < 10:
            errors.append(_("The message is too short."))

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("contact.html",
                                   form={"name": name, "email": email,
                                         "subject": subject, "body": body})

        with db.DBSession() as conn:
            if conn is None:
                flash(_("Cannot save right now. Please try again later."), "danger")
                return render_template("contact.html")
            saved = db.execute_query(
                conn,
                "INSERT INTO messages (name, email, subject, body, ip_address) "
                "VALUES (%s, %s, %s, %s, %s)",
                (name, email, subject or None, body, request.remote_addr),
            )
            if saved is None:
                flash(_("Cannot save right now. Please try again later."), "danger")
                return render_template("contact.html",
                                       form={"name": name, "email": email,
                                             "subject": subject, "body": body})

        # Ipadala ang email notification (best-effort; naka-save pa rin sa DB).
        email_failed = False
        if mailer.is_enabled():
            try:
                mailer.send_contact_notification(name, email, subject, body)
            except mailer.MailError as e:
                email_failed = True
                current_app.logger.warning("Hindi naipadala ang contact email: %s", e)

        if email_failed:
            flash(_("Your message was saved, but the email notification failed. "
                    "We will still get back to you."), "warning")
        else:
            flash(_("Thank you! Your message has been received."), "success")
        return redirect(url_for("main.contact"))

    return render_template("contact.html")


@main_bp.route("/api/assistant", methods=["POST"])
@limiter.limit("10 per minute", methods=["POST"])
def assistant_ask():
    if not assistant.is_enabled():
        return jsonify({"ok": False, "error": "disabled"}), 503

    data = request.get_json(silent=True) or {}
    question = clean(data.get("question"), current_app.config["AI_MAX_QUESTION"])
    if len(question) < 2:
        return jsonify({"ok": False, "error": "empty"}), 400

    history = data.get("history")
    if not isinstance(history, list):
        history = []

    try:
        answer = assistant.ask(question, history)
    except assistant.AssistantError as e:
        current_app.logger.warning("Assistant error: %s", e)
        return jsonify({"ok": False, "error": "error"}), 502

    return jsonify({"ok": True, "answer": answer})


@main_bp.route("/healthz")
def healthz():
    """Temporary diagnostic para sa DB config (walang buong password).
    Gamitin: /healthz?k=jonard-diag-2026  -- aalisin pagkatapos."""
    if request.args.get("k") != "jonard-diag-2026":
        abort(404)

    from config import Config

    cfg = Config.db_config()
    pw = Config.DB_PASSWORD or ""
    info = {
        "host": Config.DB_HOST,
        "port": Config.DB_PORT,
        "user": Config.DB_USER,
        "db_name": Config.DB_NAME,
        "ssl_ca": Config.DB_SSL_CA,
        "ssl_required": Config.DB_SSL_REQUIRED,
        "db_config": {k: v for k, v in cfg.items() if k != "password"},
        "pw_len": len(pw),
        "pw_head": pw[:2],
        "pw_tail": pw[-2:],
        "connected": False,
        "error": None,
        "raw_error": None,
    }

    try:
        import mysql.connector
        direct = dict(cfg)
        direct["connection_timeout"] = 10
        conn = mysql.connector.connect(**direct)
        info["connected"] = True
        conn.close()
    except Exception as e:
        info["raw_error"] = f"{type(e).__name__}: {e}"

    return jsonify(info)
