"""
app.py
------
Flask app factory para sa portfolio.

Patakbuhin (dev):
    python app.py            ->  http://127.0.0.1:5000

Seed ng admin account:
    python seed_admin.py
"""

import os

from flask import Flask, render_template, request, session, current_app
from werkzeug.middleware.proxy_fix import ProxyFix

from config import get_config
from extensions import csrf, limiter, babel


def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())

    # Behind nginx (VPS deploy): tiwala sa X-Forwarded-* headers para tama ang
    # nakikitang client IP ng rate limiter. Naka-bind ang gunicorn sa localhost,
    # kaya ligtas itong gawin.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Siguraduhing existing ang upload folder
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Gumawa ng DB + tables ONCE sa startup (best-effort; hindi nakakabit sa request)
    import database as db
    if not db.init_schema():
        app.logger.warning("Hindi ma-initialize ang database. Tumatakbo ba ang MySQL/XAMPP?")

    # --- Security extensions ---
    csrf.init_app(app)                      # CSRF token sa lahat ng forms
    limiter.init_app(app)                   # rate limiting (brute-force protection)

    # --- Language (i18n) ---
    babel.init_app(app, locale_selector=_get_locale)

    @app.context_processor
    def inject_languages():
        langs = app.config["LANGUAGES"]
        return {
            "languages": langs,
            "current_language": _get_locale(),
            "language_names": {"en": "English", "fil": "Filipino",
                               "ceb": "Bisaya"},
            "ai_enabled": bool(app.config.get("AI_API_KEY")),
            "project_categories": app.config["PROJECT_CATEGORIES"],
            "social_links": app.config["SOCIAL_LINKS"],
        }

    # --- Blueprints ---
    from blueprints.main import main_bp
    from blueprints.admin import admin_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp)

    # --- Error handlers (generic messages; hindi nag-le-leak ng details) ---
    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("404.html", message="Masyadong malaki ang file (max 4MB)."), 413

    @app.errorhandler(429)
    def too_many(e):
        return render_template("404.html", message="Masyadong maraming request. Subukan ulit mamaya."), 429

    @app.errorhandler(500)
    def server_error(e):
        return render_template("404.html", message="May error sa server."), 500

    return app


def _get_locale():
    """Piliin ang wika: (1) ?lang= sa URL, (2) session, (3) browser header."""
    languages = current_app.config["LANGUAGES"]
    default = current_app.config["BABEL_DEFAULT_LOCALE"]
    lang = request.args.get("lang")
    if lang in languages:
        session["lang"] = lang
    elif "lang" not in session:
        session["lang"] = request.accept_languages.best_match(
            languages, default=default
        )
    return session.get("lang", default)


app = create_app()


if __name__ == "__main__":
    # Naka-off ang debug by default; i-on lang sa dev gamit ang FLASK_DEBUG=1
    app.run(debug=app.config["DEBUG"], port=5000)
