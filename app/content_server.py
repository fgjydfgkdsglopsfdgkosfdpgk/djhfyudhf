"""Utilities for serving static HTML and assets from a secure root."""
from __future__ import annotations

from html import escape
import re
from pathlib import Path
from typing import Optional, Tuple

from flask import abort, make_response, redirect, request, send_from_directory
from werkzeug.exceptions import NotFound
from werkzeug.utils import safe_join


_ALLOWED_SEGMENT_RE = re.compile(r"^[A-Za-z0-9-]+$")
_ROOT_SITE = "_"


class ContentServer:
    """Serve HTML and static assets from a configurable content root."""

    def __init__(self, root: Path):
        self.root = root.resolve()

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

    def _site_root(self, site: str) -> Optional[Path]:
        directory = self.root / site
        if not directory.exists() or not directory.is_dir():
            return None
        return directory

    def _resolve_site(self, path: str) -> Tuple[str, bool, str, bool]:
        """Return ``(site_name, via_subdomain, resource_path, needs_redirect)``."""

        subdomain = self._get_subdomain()
        segments = [segment for segment in path.split("/") if segment]

        if subdomain:
            site_root = self._site_root(subdomain)
            if not site_root:
                abort(404)
            return subdomain, True, "/".join(segments), False

        if segments:
            candidate = segments[0]
            site_root = None
            if _ALLOWED_SEGMENT_RE.match(candidate):
                site_root = self._site_root(candidate)
            if site_root:
                resource_segments = segments[1:]
                needs_redirect = not resource_segments and not request.path.endswith("/")
                return candidate, False, "/".join(resource_segments), needs_redirect

        site_root = self._site_root(_ROOT_SITE)
        if not site_root:
            abort(404)
        return _ROOT_SITE, False, "/".join(segments), False

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
    def serve(self, path: str):
        site_name, via_subdomain, resource_path, needs_redirect = self._resolve_site(path)

        if needs_redirect:
            qs = ("?" + request.query_string.decode()) if request.query_string else ""
            return redirect(f"{request.path}/{qs}", code=301)

        site_root = self._site_root(site_name)
        if not site_root:
            abort(404)

        resource = resource_path or "index.html"
        if resource.endswith("/"):
            abort(404)

        base_href = "/" if via_subdomain or site_name == _ROOT_SITE else f"/{site_name}/"

        if resource in {"", "index.html"}:
            return self._serve_html(site_root, "index.html", base_href)

        return self._serve_static(site_root, resource)


__all__ = ["ContentServer"]
