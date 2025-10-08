"""Utilities for serving static HTML and assets from a secure root."""
from __future__ import annotations

from html import escape
import re
from pathlib import Path
from typing import Optional

from flask import abort, make_response, redirect, request, send_from_directory
from werkzeug.exceptions import NotFound
from werkzeug.utils import safe_join


_ALLOWED_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ContentServer:
    """Serve HTML and static assets from a configurable content root.

    The original implementation relied heavily on ``os.path.join`` which made it
    possible to traverse outside of the intended directory tree using path
    components such as ``..``.  This class centralises the logic for resolving
    paths and ensures that every path is validated before it is used.
    """

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
            # Missing directories should be treated as absent resources.
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

        m = re.search(r"<head([^>]*)>", html_text, flags=re.I)
        insert = f'<base href="{base_href}">'
        if m:
            pos = m.end()
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
        subdomain = self._get_subdomain()

        # Redirect ``/site`` -> ``/site/`` when the directory exists.
        if path and "/" not in path.rstrip("/"):
            if self._valid_directory(path):
                if not request.path.endswith("/"):
                    qs = ("?" + request.query_string.decode()) if request.query_string else ""
                    return redirect(f"{request.path}/{qs}", code=301)

        explicit_response = self._serve_explicit_prefix(path)
        if explicit_response is not None:
            return explicit_response

        if subdomain:
            subdomain_response = self._serve_subdomain(subdomain, path)
            if subdomain_response is not None:
                return subdomain_response

        return self._serve_global(path)

    # ------------------------------------------------------------------
    # Serving strategies
    # ------------------------------------------------------------------
    def _serve_explicit_prefix(self, path: str):
        path_parts = [p for p in path.split("/") if p]
        if not path_parts:
            return None

        possible_sub = path_parts[0]
        if not _ALLOWED_SEGMENT_RE.match(possible_sub):
            return None

        if possible_sub in {"static", "html"}:
            return None

        sub_dir = self.root / possible_sub
        if not sub_dir.is_dir():
            return None

        sub_path = "/".join(path_parts[1:])
        if sub_path.startswith("static/"):
            return self._serve_static(sub_dir / "static", sub_path[len("static/"):])

        html_dir = sub_dir / "html"
        if sub_path in ("", "html/index.html"):
            return self._serve_html(html_dir, "index.html", f"/{possible_sub}/")

        return self._serve_html(html_dir, sub_path, f"/{possible_sub}/")

    def _serve_subdomain(self, subdomain: str, path: str):
        sub_dir = self.root / subdomain
        if not sub_dir.is_dir():
            return None

        if path.startswith("static/"):
            return self._serve_static(sub_dir / "static", path[len("static/"):])

        html_dir = sub_dir / "html"
        if path in ("", "html/index.html"):
            return self._serve_html(html_dir, "index.html", "/")

        return self._serve_html(html_dir, path, "/")

    def _serve_global(self, path: str):
        if path.startswith("static/"):
            return self._serve_static(self.root / "static", path[len("static/"):])

        html_dir = self.root / "html"
        if path in ("", "html/index.html"):
            return self._serve_html(html_dir, "index.html", "/")

        return self._serve_html(html_dir, path, "/")

    def _valid_directory(self, segment: str) -> bool:
        if not _ALLOWED_SEGMENT_RE.match(segment):
            return False
        candidate = self.root / segment
        return candidate.is_dir()


__all__ = ["ContentServer"]
