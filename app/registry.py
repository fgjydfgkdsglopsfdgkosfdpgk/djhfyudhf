"""Registry and storage helpers for managing subsites with versioning."""
from __future__ import annotations

import json
import secrets
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

_TEXT_LIMIT_BYTES = 5 * 1024 * 1024  # 5 MiB per text asset


class SiteLifecycle(str, Enum):
    """High level state for a site."""

    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"
    DELETED = "deleted"


class SiteVersionStatus(str, Enum):
    """Moderation status for a particular version."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class SiteVersion:
    """Metadata describing a stored version of a site."""

    version_id: str
    status: SiteVersionStatus
    preview_token: str
    created_at: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "version_id": self.version_id,
            "status": self.status.value,
            "preview_token": self.preview_token,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, str]) -> "SiteVersion":
        return cls(
            version_id=payload["version_id"],
            status=SiteVersionStatus(payload["status"]),
            preview_token=payload.get("preview_token", ""),
            created_at=payload.get("created_at", datetime.now(tz=timezone.utc).isoformat()),
        )


@dataclass
class SiteRecord:
    """Stored metadata for a site."""

    name: str
    owner_id: str
    owner_token: str
    lifecycle: SiteLifecycle
    active_version: Optional[str] = None
    versions: Dict[str, SiteVersion] = field(default_factory=dict)

    def to_dict(self, include_tokens: bool = False) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "name": self.name,
            "owner_id": self.owner_id,
            "lifecycle": self.lifecycle.value,
            "active_version": self.active_version,
            "versions": {key: version.to_dict() for key, version in self.versions.items()},
        }
        if include_tokens:
            payload["owner_token"] = self.owner_token
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "SiteRecord":
        versions_payload = payload.get("versions", {}) or {}
        versions = {
            name: SiteVersion.from_dict(data) for name, data in versions_payload.items()
        }
        return cls(
            name=str(payload["name"]),
            owner_id=str(payload["owner_id"]),
            owner_token=str(payload.get("owner_token", "")),
            lifecycle=SiteLifecycle(str(payload.get("lifecycle", SiteLifecycle.PENDING.value))),
            active_version=payload.get("active_version"),
            versions=versions,
        )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def pending_version(self) -> Optional[SiteVersion]:
        for version in self.versions.values():
            if version.status == SiteVersionStatus.PENDING:
                return version
        return None

    def approved_versions(self) -> Dict[str, SiteVersion]:
        return {
            vid: version for vid, version in self.versions.items() if version.status == SiteVersionStatus.APPROVED
        }


class SiteRegistryError(RuntimeError):
    """Base exception for registry operations."""


class SiteExistsError(SiteRegistryError):
    """Raised when attempting to create a site that already exists."""


class SiteNotFoundError(SiteRegistryError):
    """Raised when a site is not registered."""


class SiteOwnershipError(SiteRegistryError):
    """Raised when an owner token does not match the stored token."""


class SiteFrozenError(SiteRegistryError):
    """Raised when updates are attempted on a blocked site."""


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
            # Ensure owner token exists for legacy entries.
            if not record.owner_token:
                record.owner_token = secrets.token_urlsafe(24)
            self._sites[name] = record

    def _dump(self) -> None:
        data = {name: record.to_dict(include_tokens=True) for name, record in self._sites.items()}
        tmp_path = self._store_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self._store_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _validate_name(self, name: str) -> None:
        if not name:
            raise ValueError("Site name is required")
        if name == "_":
            return
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
        if any(ch not in allowed for ch in name):
            raise ValueError("Site name may contain only alphanumeric characters and hyphen")

    def _require(self, name: str) -> SiteRecord:
        record = self._sites.get(name)
        if not record:
            raise SiteNotFoundError(name)
        return record

    def _version_dir(self, name: str, version_id: str) -> Path:
        return self.root / name / "versions" / version_id

    def _live_dir(self, name: str) -> Path:
        return self.root / name / "live"

    def _ensure_limits(self, filename: str, data: str) -> None:
        if len(data.encode("utf-8")) > _TEXT_LIMIT_BYTES:
            raise ValueError(f"{filename} превышает лимит 5 МБ")

    def _write_version_files(self, name: str, version_id: str, html: str, css: str, js: str) -> None:
        self._ensure_limits("index.html", html)
        self._ensure_limits("index.css", css)
        self._ensure_limits("index.js", js)
        version_dir = self._version_dir(name, version_id)
        version_dir.mkdir(parents=True, exist_ok=True)
        (version_dir / "index.html").write_text(html, encoding="utf-8")
        (version_dir / "index.css").write_text(css, encoding="utf-8")
        (version_dir / "index.js").write_text(js, encoding="utf-8")

    def _read_bundle(self, directory: Path) -> Optional[Dict[str, str]]:
        try:
            html = (directory / "index.html").read_text(encoding="utf-8")
            css = (directory / "index.css").read_text(encoding="utf-8")
            js = (directory / "index.js").read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        return {"html": html, "css": css, "js": js}

    def _bundle_timestamp(self, directory: Path) -> str:
        mtimes = []
        for name in ("index.html", "index.css", "index.js"):
            path = directory / name
            if path.exists():
                mtimes.append(path.stat().st_mtime)
        if not mtimes:
            return datetime.now(tz=timezone.utc).isoformat()
        return datetime.fromtimestamp(max(mtimes), tz=timezone.utc).isoformat()

    def _read_version_file(self, name: str, version_id: str, filename: str) -> str:
        path = self._version_dir(name, version_id) / filename
        if not path.exists():
            raise SiteNotFoundError(name)
        return path.read_text(encoding="utf-8")

    def _next_version_id(self, record: SiteRecord) -> str:
        suffix = 1
        for version_id in record.versions.keys():
            if version_id.startswith("v"):
                try:
                    suffix = max(suffix, int(version_id[1:]) + 1)
                except ValueError:
                    continue
        return f"v{suffix}"

    def _copy_to_live(self, name: str, version_id: str) -> None:
        live_dir = self._live_dir(name)
        live_dir.mkdir(parents=True, exist_ok=True)
        source = self._version_dir(name, version_id)
        for filename in ("index.html", "index.css", "index.js"):
            data = (source / filename).read_text(encoding="utf-8")
            (live_dir / filename).write_text(data, encoding="utf-8")

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
        lifecycle: SiteLifecycle = SiteLifecycle.ACTIVE,
    ) -> SiteRecord:
        self._validate_name(name)
        record = self._sites.get(name)
        if record:
            return record
        owner_token = secrets.token_urlsafe(24)
        version_id = "v1"
        site_root = self.root / name
        versions_root = site_root / "versions"
        existing_versions = []
        if versions_root.exists():
            for candidate in sorted(versions_root.iterdir()):
                if not candidate.is_dir():
                    continue
                bundle = self._read_bundle(candidate)
                if not bundle:
                    continue
                existing_versions.append(
                    (
                        candidate.name,
                        bundle,
                        self._bundle_timestamp(candidate),
                    )
                )

        live_bundle = self._read_bundle(site_root / "live")

        if existing_versions:
            version_records: Dict[str, SiteVersion] = {}
            bundle_map = {version_name: bundle for version_name, bundle, _ in existing_versions}
            for existing_id, _, created_at in existing_versions:
                version_records[existing_id] = SiteVersion(
                    version_id=existing_id,
                    status=
                    SiteVersionStatus.APPROVED
                    if lifecycle == SiteLifecycle.ACTIVE
                    else SiteVersionStatus.PENDING,
                    preview_token="",
                    created_at=created_at,
                )

            active_version = None
            if live_bundle:
                for existing_id, bundle in bundle_map.items():
                    if bundle == live_bundle:
                        active_version = existing_id
                        break

            if lifecycle == SiteLifecycle.ACTIVE and not active_version and existing_versions:
                active_version = existing_versions[-1][0]

            record = SiteRecord(
                name=name,
                owner_id=owner_id,
                owner_token=owner_token,
                lifecycle=lifecycle,
                active_version=active_version if lifecycle == SiteLifecycle.ACTIVE else None,
                versions=version_records,
            )
            self._sites[name] = record
            if (
                record.lifecycle == SiteLifecycle.ACTIVE
                and record.active_version
                and (
                    not live_bundle
                    or bundle_map.get(record.active_version) != live_bundle
                )
            ):
                self._copy_to_live(name, record.active_version)
            self._dump()
            return record

        html_path = site_root / "index.html"
        css_path = site_root / "index.css"
        js_path = site_root / "index.js"
        bundle = self._read_bundle(site_root)
        if not bundle:
            bundle = live_bundle or {
                "html": html_path.read_text(encoding="utf-8") if html_path.exists() else "",
                "css": css_path.read_text(encoding="utf-8") if css_path.exists() else "",
                "js": js_path.read_text(encoding="utf-8") if js_path.exists() else "",
            }
        self._write_version_files(name, version_id, bundle["html"], bundle["css"], bundle["js"])
        record = SiteRecord(
            name=name,
            owner_id=owner_id,
            owner_token=owner_token,
            lifecycle=lifecycle,
            active_version=version_id if lifecycle == SiteLifecycle.ACTIVE else None,
            versions={
                version_id: SiteVersion(
                    version_id=version_id,
                    status=SiteVersionStatus.APPROVED if lifecycle == SiteLifecycle.ACTIVE else SiteVersionStatus.PENDING,
                    preview_token="",
                    created_at=datetime.now(tz=timezone.utc).isoformat(),
                )
            },
        )
        self._sites[name] = record
        if record.active_version:
            self._copy_to_live(name, record.active_version)
        self._dump()
        return record

    def read_content(self, name: str, version_id: Optional[str] = None) -> Dict[str, str]:
        record = self._require(name)
        target_version = version_id or record.active_version
        if not target_version:
            pending = record.pending_version()
            if not pending:
                raise SiteNotFoundError(name)
            target_version = pending.version_id
        data = {
            "html": self._read_version_file(name, target_version, "index.html"),
            "css": self._read_version_file(name, target_version, "index.css"),
            "js": self._read_version_file(name, target_version, "index.js"),
            "version_id": target_version,
        }
        return data

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
        owner_token = secrets.token_urlsafe(32)
        version_id = "v1"
        preview_token = secrets.token_urlsafe(32)
        self._write_version_files(name, version_id, html, css, js)
        record = SiteRecord(
            name=name,
            owner_id=owner_id,
            owner_token=owner_token,
            lifecycle=SiteLifecycle.PENDING,
            active_version=None,
            versions={
                version_id: SiteVersion(
                    version_id=version_id,
                    status=SiteVersionStatus.PENDING,
                    preview_token=preview_token,
                    created_at=datetime.now(tz=timezone.utc).isoformat(),
                )
            },
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
        if record.owner_token != owner_token:
            raise SiteOwnershipError(name)
        if record.lifecycle == SiteLifecycle.BLOCKED:
            raise SiteFrozenError(name)
        pending = record.pending_version()
        if pending:
            version = pending
        else:
            version_id = self._next_version_id(record)
            version = SiteVersion(
                version_id=version_id,
                status=SiteVersionStatus.PENDING,
                preview_token="",
                created_at=datetime.now(tz=timezone.utc).isoformat(),
            )
            record.versions[version_id] = version
        self._write_version_files(name, version.version_id, html, css, js)
        version.preview_token = secrets.token_urlsafe(32)
        version.status = SiteVersionStatus.PENDING
        version.created_at = datetime.now(tz=timezone.utc).isoformat()
        record.lifecycle = SiteLifecycle.PENDING if not record.active_version else record.lifecycle
        self._dump()
        return record

    def approve(self, name: str) -> SiteRecord:
        record = self._require(name)
        pending = record.pending_version()
        if not pending:
            raise SiteRegistryError("No pending version to approve")
        pending.status = SiteVersionStatus.APPROVED
        pending.preview_token = ""
        record.active_version = pending.version_id
        record.lifecycle = SiteLifecycle.ACTIVE
        self._copy_to_live(name, pending.version_id)
        self._dump()
        return record

    def reject(self, name: str) -> SiteRecord:
        record = self._require(name)
        pending = record.pending_version()
        if not pending:
            raise SiteRegistryError("No pending version to reject")
        pending.status = SiteVersionStatus.REJECTED
        record.lifecycle = SiteLifecycle.BLOCKED
        record.active_version = None
        live_dir = self._live_dir(name)
        if live_dir.exists():
            shutil.rmtree(live_dir)
        self._dump()
        return record

    def delete_site(self, name: str, *, owner_token: str, purge: bool = False) -> None:
        record = self._require(name)
        if record.owner_token != owner_token:
            raise SiteOwnershipError(name)
        site_root = self.root / name
        if purge and site_root.exists():
            shutil.rmtree(site_root)
        self._sites.pop(name, None)
        self._dump()

    def set_active_version(self, name: str, *, owner_token: str, version_id: str) -> SiteRecord:
        record = self._require(name)
        if record.owner_token != owner_token:
            raise SiteOwnershipError(name)
        version = record.versions.get(version_id)
        if not version or version.status != SiteVersionStatus.APPROVED:
            raise SiteRegistryError("Version is not approved")
        record.active_version = version_id
        record.lifecycle = SiteLifecycle.ACTIVE
        self._copy_to_live(name, version_id)
        self._dump()
        return record

    def delete_version(self, name: str, *, owner_token: str, version_id: str) -> SiteRecord:
        record = self._require(name)
        if record.owner_token != owner_token:
            raise SiteOwnershipError(name)
        if record.active_version == version_id:
            raise SiteRegistryError("Cannot delete the active version")
        version = record.versions.get(version_id)
        if not version or version.status == SiteVersionStatus.PENDING:
            raise SiteRegistryError("Cannot delete version")
        version_dir = self._version_dir(name, version_id)
        if version_dir.exists():
            shutil.rmtree(version_dir)
        record.versions.pop(version_id, None)
        self._dump()
        return record


__all__ = [
    "SiteRegistry",
    "SiteRecord",
    "SiteVersion",
    "SiteLifecycle",
    "SiteVersionStatus",
    "SiteRegistryError",
    "SiteExistsError",
    "SiteNotFoundError",
    "SiteOwnershipError",
    "SiteFrozenError",
]
