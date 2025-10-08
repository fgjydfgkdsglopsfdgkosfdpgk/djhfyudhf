"""Application factory for the static content server."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from flask import Flask

from .accounts import AccountStore
from .content_server import ContentServer
from .notifications import FreezingNotifier, ModerationNotifier, NullNotifier
from .registry import SiteRegistry
from .support import SupportStore
from .web import create_web_blueprint


def create_app(
    content_root: Optional[Path] = None,
    *,
    registry: SiteRegistry | None = None,
    notifier: ModerationNotifier | None = None,
    accounts: AccountStore | None = None,
    support: SupportStore | None = None,
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

    base_notifier = notifier or NullNotifier()
    account_store = accounts or AccountStore(root)
    support_store = support or SupportStore(root)
    active_notifier = FreezingNotifier(base_notifier, account_store)

    app.config.setdefault("MODERATION_NOTIFIER", active_notifier)
    app.config.setdefault("SITE_REGISTRY", registry)
    app.config.setdefault("ACCOUNT_STORE", account_store)
    app.config.setdefault("SUPPORT_STORE", support_store)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = "dev-secret-key"
    app.secret_key = app.config["SECRET_KEY"]

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

    app.register_blueprint(
        create_web_blueprint(
            registry,
            accounts=account_store,
            support=support_store,
            notifier=active_notifier,
        )
    )

    return app


__all__ = ["create_app"]
