"""Application factory for the static content server."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from flask import Flask

from .content_server import ContentServer


def create_app(content_root: Optional[Path] = None) -> Flask:
    """Create and configure the Flask application."""

    default_root = Path(__file__).resolve().parent / "sites"
    root = Path(content_root or default_root).resolve()
    server = ContentServer(root)

    app = Flask(__name__, static_folder=None)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve(path: str):
        return server.serve(path)

    return app


__all__ = ["create_app"]
