"""Registry and storage helpers for managing subsites."""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional


class SiteStatus(str, Enum):
    """Lifecycle states for a registered site."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class SiteRecord:
    """Stored metadata for a subsite."""

    name: str
    owner_id: str
    owner_token: str
    preview_token: str
    status: SiteStatus

    def to_dict(self, include_tokens: bool = False) -> Dict[str, str]:
        data: Dict[str, str] = {
            "name": self.name,
            "owner_id": self.owner_id,
            "status": self.status.value,
        }
        if include_tokens:
            data["owner_token"] = self.owner_token
            data["preview_token"] = self.preview_token
        return data

    @classmethod
    def from_dict(cls, payload: Dict[str, str]) -> "SiteRecord":
        return cls(
            name=payload["name"],
            owner_id=payload["owner_id"],
            owner_token=payload["owner_token"],
            preview_token=payload["preview_token"],
            status=SiteStatus(payload["status"]),
        )


class SiteRegistryError(RuntimeError):
    """Base exception for registry operations."""


class SiteExistsError(SiteRegistryError):
    """Raised when attempting to create a site that already exists."""


class SiteNotFoundError(SiteRegistryError):
    """Raised when a site is not registered."""


class SiteOwnershipError(SiteRegistryError):
    """Raised when an owner token does not match the stored token."""


class SiteFrozenError(SiteRegistryError):
    """Raised when updates are attempted on a rejected site."""


class SiteRegistry:
    """Persistent registry for subsite metadata and content."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._store_path = self.root / "_registry.json"
        self._sites: Dict[str, SiteRecord] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self._store_path.exists():
            return
        data = json.loads(self._store_path.read_text(encoding="utf-8"))
        for name, payload in data.items():
            record = SiteRecord.from_dict(payload)
            self._sites[name] = record

    def _dump(self) -> None:
        data = {name: record.to_dict(include_tokens=True) for name, record in self._sites.items()}
        tmp_path = self._store_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self._store_path)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def _validate_name(self, name: str) -> None:
        if not name:
            raise ValueError("Site name is required")
        if name == "_":
            return
        if any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for ch in name):
            raise ValueError("Site name may contain only alphanumeric characters and hyphen")

    def _require(self, name: str) -> SiteRecord:
        record = self._sites.get(name)
        if not record:
            raise SiteNotFoundError(name)
        return record

    def _write_files(self, name: str, html: str, css: str, js: str) -> None:
        site_dir = self.root / name
        site_dir.mkdir(parents=True, exist_ok=True)
        (site_dir / "index.html").write_text(html, encoding="utf-8")
        (site_dir / "index.css").write_text(css, encoding="utf-8")
        (site_dir / "index.js").write_text(js, encoding="utf-8")

    # ------------------------------------------------------------------
    # Public operations
    # ------------------------------------------------------------------
    def list_sites(self) -> Dict[str, SiteRecord]:
        return dict(self._sites)

    def get(self, name: str) -> Optional[SiteRecord]:
        return self._sites.get(name)

    def register_existing_site(
        self,
        name: str,
        *,
        owner_id: str = "system",
        status: SiteStatus = SiteStatus.APPROVED,
    ) -> SiteRecord:
        self._validate_name(name)
        record = self._sites.get(name)
        if record:
            return record
        owner_token = secrets.token_urlsafe(16)
        preview_token = secrets.token_urlsafe(16)
        record = SiteRecord(
            name=name,
            owner_id=owner_id,
            owner_token=owner_token,
            preview_token=preview_token,
            status=status,
        )
        self._sites[name] = record
        self._dump()
        return record

    def create_site(
        self,
        name: str,
        *,
        owner_id: str,
        html: str,
        css: str,
        js: str,
    ) -> SiteRecord:
        self._validate_name(name)
        if name in self._sites:
            raise SiteExistsError(name)
        owner_token = secrets.token_urlsafe(24)
        preview_token = secrets.token_urlsafe(24)
        self._write_files(name, html, css, js)
        record = SiteRecord(
            name=name,
            owner_id=owner_id,
            owner_token=owner_token,
            preview_token=preview_token,
            status=SiteStatus.PENDING,
        )
        self._sites[name] = record
        self._dump()
        return record

    def update_content(
        self,
        name: str,
        *,
        owner_token: str,
        html: str,
        css: str,
        js: str,
    ) -> SiteRecord:
        record = self._require(name)
        if record.status == SiteStatus.REJECTED:
            raise SiteFrozenError(name)
        if owner_token != record.owner_token:
            raise SiteOwnershipError(name)
        self._write_files(name, html, css, js)
        record.preview_token = secrets.token_urlsafe(24)
        record.status = SiteStatus.PENDING
        self._dump()
        return record

    def approve(self, name: str) -> SiteRecord:
        record = self._require(name)
        record.status = SiteStatus.APPROVED
        self._dump()
        return record

    def reject(self, name: str) -> SiteRecord:
        record = self._require(name)
        record.status = SiteStatus.REJECTED
        self._dump()
        return record


__all__ = [
    "SiteRegistry",
    "SiteRecord",
    "SiteStatus",
    "SiteRegistryError",
    "SiteExistsError",
    "SiteNotFoundError",
    "SiteOwnershipError",
    "SiteFrozenError",
]
