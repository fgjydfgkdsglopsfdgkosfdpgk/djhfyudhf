"""Entry point for running the Flask development server."""
from __future__ import annotations

import os
from pathlib import Path

from app import create_app
from app.accounts import AccountStore
from app.registry import SiteRegistry
from app.support import SupportStore
from app.telegram_bot import TelegramModerationBot


def build_app():
    root = Path(
        os.environ.get(
            "CONTENT_ROOT",
            Path(__file__).resolve().parent / "app" / "sites",
        )
    ).resolve()

    registry = SiteRegistry(root)
    account_store = AccountStore(root)
    support_store = SupportStore(root)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_ADMIN_CHAT")
    base_url = os.environ.get("SITE_BASE_URL", "http://localhost")

    bot = None
    notifier = None
    if token and chat_id:
        bot = TelegramModerationBot(
            token=token,
            registry=registry,
            accounts=account_store,
            admin_chat_id=int(chat_id),
            base_url=base_url,
        )
        notifier = bot

    app = create_app(
        root,
        registry=registry,
        notifier=notifier,
        accounts=account_store,
        support=support_store,
    )

    if bot:
        app.telegram_bot = bot  # type: ignore[attr-defined]
        bot.start_background()

    return app


app = build_app()


if __name__ == "__main__":
    app.run(port=80, debug=True)
