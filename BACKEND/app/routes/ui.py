"""Serve the browser UI from the same origin as the API.

These routes only deliver static HTML/CSS/JS files from the UI folder. They do
not expose the database or implement any business logic. Keeping the UI on the
same origin means the session cookie and the RBAC-protected APIs work without
CORS configuration.
"""

from pathlib import Path

from flask import Blueprint, abort, send_from_directory


UI_DIR = Path(__file__).resolve().parents[3] / "UI"
ALLOWED_SUFFIXES = frozenset({".html", ".css", ".js"})

ui_bp = Blueprint("ui", __name__)


def _send(folder, filename):
    if Path(filename).suffix.lower() not in ALLOWED_SUFFIXES:
        abort(404)
    return send_from_directory(UI_DIR / folder, filename)


@ui_bp.route("/")
def index():
    """Serve the login page."""

    return _send(".", "index.html")


@ui_bp.route("/pages/<path:filename>")
def page(filename):
    """Serve a UI page."""

    return _send("pages", filename)


@ui_bp.route("/css/<path:filename>")
def stylesheet(filename):
    """Serve a stylesheet."""

    return _send("css", filename)


@ui_bp.route("/js/<path:filename>")
def script(filename):
    """Serve a JavaScript file."""

    return _send("js", filename)
