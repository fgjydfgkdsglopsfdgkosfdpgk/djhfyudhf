"""Notification helpers for moderation events."""
from __future__ import annotations

from typing import Protocol

from .accounts import AccountStore
from .registry import SiteRecord


class ModerationNotifier(Protocol):
    """Protocol for sending moderation lifecycle notifications."""

    def site_pending(self, record: SiteRecord) -> None:
        """Notify that a site requires moderator review."""

    def site_approved(self, record: SiteRecord) -> None:
        """Notify that a site has been approved."""

    def site_rejected(self, record: SiteRecord) -> None:
        """Notify that a site has been rejected."""


class NullNotifier:
    """Fallback notifier that ignores all events."""

    def site_pending(self, record: SiteRecord) -> None:  # pragma: no cover - intentionally empty
        return

    def site_approved(self, record: SiteRecord) -> None:  # pragma: no cover - intentionally empty
        return

    def site_rejected(self, record: SiteRecord) -> None:  # pragma: no cover - intentionally empty
        return


class FreezingNotifier:
    """Notifier wrapper that freezes owners on rejection when required."""

    def __init__(self, delegate: ModerationNotifier, accounts: AccountStore):
        self.delegate = delegate
        self.accounts = accounts

    def site_pending(self, record: SiteRecord) -> None:
        self.delegate.site_pending(record)

    def site_approved(self, record: SiteRecord) -> None:
        self.delegate.site_approved(record)

    def site_rejected(self, record: SiteRecord) -> None:
        if record.approved_versions():
            try:
                self.accounts.freeze(record.owner_id)
            except KeyError:  # pragma: no cover - defensive
                pass
        self.delegate.site_rejected(record)


__all__ = ["ModerationNotifier", "NullNotifier", "FreezingNotifier"]
