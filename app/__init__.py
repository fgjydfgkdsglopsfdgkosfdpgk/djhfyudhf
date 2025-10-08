"""Application factory for the static content server."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from flask import Flask

from .content_server import ContentServer


def create_app(content_root: Optional[Path] = None) -> Flask:
    """Create and configure the Flask application.

    Parameters
    ----------
    content_root:
        Base directory that contains the ``html`` and ``static`` folders as well as
        optional sub-directories for subdomain specific content.  When omitted the
        directory that contains this module is used.
    """

    root = Path(content_root or Path(__file__).resolve().parent).resolve()
    server = ContentServer(root)

    app = Flask(__name__, static_folder=None)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve(path: str):
        return server.serve(path)

    return app


__all__ = ["create_app"]
