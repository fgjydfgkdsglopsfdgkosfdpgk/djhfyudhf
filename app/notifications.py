"""Notification helpers for moderation events."""
from __future__ import annotations

from typing import Protocol

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


__all__ = ["ModerationNotifier", "NullNotifier"]
