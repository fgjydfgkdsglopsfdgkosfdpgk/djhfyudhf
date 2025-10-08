"""Application factory for the static content server."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from flask import Flask

from .api import create_api_blueprint
from .content_server import ContentServer
from .notifications import ModerationNotifier, NullNotifier
from .registry import SiteRegistry


def create_app(
    content_root: Optional[Path] = None,
    *,
    registry: SiteRegistry | None = None,
    notifier: ModerationNotifier | None = None,
) -> Flask:
    """Create and configure the Flask application."""

    default_root = Path(__file__).resolve().parent / "sites"
    if registry is None:
        root = Path(content_root or default_root).resolve()
        registry = SiteRegistry(root)
    else:
        root = Path(content_root or registry.root).resolve()

    server = ContentServer(root, registry)

    app = Flask(__name__, static_folder=None)
    app.config.setdefault("ADMIN_TOKEN", "changeme-admin-token")
    app.config.setdefault("SITE_BASE_URL", "http://localhost")

    active_notifier = notifier or NullNotifier()
    app.config.setdefault("MODERATION_NOTIFIER", active_notifier)
    app.config.setdefault("SITE_REGISTRY", registry)

    # Bootstrap existing directories as approved sites.
    for candidate in root.iterdir():
        if not candidate.is_dir():
            continue
        try:
            registry.register_existing_site(candidate.name)
        except ValueError:
            continue

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve(path: str):
        return server.serve(path)

    app.register_blueprint(create_api_blueprint(registry, notifier=active_notifier))

    return app


__all__ = ["create_app"]
