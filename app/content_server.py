"""Utilities for serving static HTML and assets from a secure root."""
from __future__ import annotations

from html import escape
import re
from pathlib import Path
from typing import Optional, Tuple

from flask import abort, make_response, redirect, request, send_from_directory
from werkzeug.exceptions import NotFound
from werkzeug.utils import safe_join

from .registry import SiteLifecycle, SiteRecord, SiteRegistry


_ALLOWED_SEGMENT_RE = re.compile(r"^[A-Za-z0-9-]+$")
_ROOT_SITE = "_"


class ContentServer:
    """Serve HTML and static assets from a configurable content root."""

    def __init__(self, root: Path, registry: SiteRegistry):
        self.root = root.resolve()
        self.registry = registry

    # ------------------------------------------------------------------
    # Request helpers
    # ------------------------------------------------------------------
    def _get_subdomain(self) -> Optional[str]:
        host = request.host.split(":", 1)[0]
        parts = host.split(".")
        if len(parts) < 2:
            return None

        if parts[-1] == "localhost":
            if len(parts) == 1:
                return None
            candidate = parts[0]
        elif len(parts) > 2:
            candidate = parts[0]
        else:
            return None

        return candidate if _ALLOWED_SEGMENT_RE.match(candidate) else None

    def _live_root(self, site: str) -> Path:
        return (self.root / site / "live").resolve()

    def _version_root(self, site: str, version_id: str) -> Path:
        return (self.root / site / "versions" / version_id).resolve()

    def _resolve_site(
        self, path: str
    ) -> Tuple[str, Optional[SiteRecord], bool, Optional[str], bool, bool]:
        """Return ``(site, record, via_subdomain, resource_path, needs_redirect, unregistered)``."""

        subdomain = self._get_subdomain()
        segments = [segment for segment in path.split("/") if segment]

        if subdomain:
            record = self.registry.get(subdomain)
            if record:
                return subdomain, record, True, "/".join(segments), False, False
            if _ALLOWED_SEGMENT_RE.match(subdomain):
                return subdomain, None, True, None, False, True
            abort(404)

        if segments:
            candidate = segments[0]
            if _ALLOWED_SEGMENT_RE.match(candidate):
                record = self.registry.get(candidate)
                if record:
                    resource_segments = segments[1:]
                    needs_redirect = not resource_segments and not request.path.endswith("/")
                    return candidate, record, False, "/".join(resource_segments), needs_redirect, False
                return candidate, None, False, None, False, True

        resource = "/".join(segments)
        record = self.registry.get(_ROOT_SITE)
        if not record:
            abort(404)
        return _ROOT_SITE, record, False, resource, False, False

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    def _safe_path(self, directory: Path, relative_path: str) -> Optional[Path]:
        """Return a path inside ``directory`` or ``None`` when invalid."""

        if relative_path.startswith("/"):
            return None

        try:
            safe = safe_join(str(directory), relative_path)
        except (NotFound, ValueError):
            return None

        if safe is None:
            return None

        resolved = Path(safe).resolve()
        try:
            directory_resolved = directory.resolve()
        except FileNotFoundError:
            return None

        if directory_resolved not in resolved.parents and resolved != directory_resolved:
            return None

        return resolved

    def _inject_base(self, html_text: str, base_href: str) -> str:
        base_href = escape(base_href, quote=True)
        if re.search(r"<base\s", html_text, flags=re.I):
            return re.sub(
                r"(<base[^>]*href=[\"\'])([^\"\']*)([\"\'][^>]*>)",
                r"\1" + base_href + r"\3",
                html_text,
                flags=re.I,
            )

        match = re.search(r"<head([^>]*)>", html_text, flags=re.I)
        insert = f'<base href="{base_href}">'
        if match:
            pos = match.end()
            return html_text[:pos] + insert + html_text[pos:]
        return insert + html_text

    def _serve_html(self, directory: Path, filename: str, base_href: str):
        safe_path = self._safe_path(directory, filename)
        if not safe_path or not safe_path.is_file():
            abort(404)

        html = safe_path.read_text(encoding="utf-8")
        html = self._inject_base(html, base_href)

        resp = make_response(html)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp

    def _serve_static(self, directory: Path, filename: str):
        safe_path = self._safe_path(directory, filename)
        if not safe_path or not safe_path.is_file():
            abort(404)
        relative = safe_path.relative_to(directory.resolve())
        return send_from_directory(str(directory.resolve()), str(relative))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def _has_preview_access(self, record: SiteRecord) -> bool:
        pending = record.pending_version()
        if not pending:
            return False
        token = request.headers.get("X-Preview-Token") or request.args.get("preview_token")
        return bool(token) and token == pending.preview_token

    def _unregistered_site(self, site: str):
        site = escape(site)
        body = (
            "<!doctype html>"
            "<html lang=\"ru\">"
            "<head><meta charset=\"utf-8\"><title>Поддомен свободен</title></head>"
            "<body>"
            f"<h1>Поддомен «{site}» не зарегистрирован</h1>"
            "<p>Этот поддомен может быть вашим. Хотите занять его? Это бесплатно!</p>"
            "</body></html>"
        )
        resp = make_response(body, 404)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp

    def _pending_site(self, record: SiteRecord):
        site = escape(record.name)
        body = (
            "<!doctype html>"
            "<html lang=\"ru\">"
            "<head><meta charset=\"utf-8\"><title>Сайт на проверке</title></head>"
            "<body>"
            f"<h1>Сайт «{site}» ожидает модерации</h1>"
            "<p>Пока страница доступна только владельцу. Загляните позже.</p>"
            "</body></html>"
        )
        resp = make_response(body, 403)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp

    def _rejected_site(self, record: SiteRecord):
        site = escape(record.name)
        body = (
            "<!doctype html>"
            "<html lang=\"ru\">"
            "<head><meta charset=\"utf-8\"><title>Сайт заблокирован</title></head>"
            "<body>"
            f"<h1>Сайт «{site}» заблокирован</h1>"
            "<p>Обратитесь в поддержку, если считаете блокировку ошибочной.</p>"
            "</body></html>"
        )
        resp = make_response(body, 403)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp

    def serve(self, path: str):
        (
            site_name,
            record,
            via_subdomain,
            resource_path,
            needs_redirect,
            unregistered,
        ) = self._resolve_site(path)

        if unregistered:
            return self._unregistered_site(site_name)

        if not record:
            abort(404)

        if needs_redirect:
            qs = ("?" + request.query_string.decode()) if request.query_string else ""
            return redirect(f"{request.path}/{qs}", code=301)

        if record.lifecycle == SiteLifecycle.DELETED:
            return self._unregistered_site(site_name)

        if record.lifecycle == SiteLifecycle.BLOCKED:
            return self._rejected_site(record)

        pending = record.pending_version()
        preview_granted = bool(pending and self._has_preview_access(record))

        if preview_granted and pending:
            site_root = self._version_root(site_name, pending.version_id)
        else:
            if not record.active_version:
                return self._pending_site(record)
            site_root = self._live_root(site_name)

        resource = (resource_path or "index.html") if resource_path is not None else "index.html"
        if resource.endswith("/"):
            abort(404)

        base_href = "/" if via_subdomain or site_name == _ROOT_SITE else f"/{site_name}/"

        if resource in {"", "index.html"}:
            return self._serve_html(site_root, "index.html", base_href)

        return self._serve_static(site_root, resource)


__all__ = ["ContentServer"]
