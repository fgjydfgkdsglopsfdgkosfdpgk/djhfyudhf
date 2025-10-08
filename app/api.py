"""HTTP API for managing subsite registration and content."""
from __future__ import annotations

from http import HTTPStatus
import textwrap

from flask import Blueprint, current_app, jsonify, request

from .notifications import ModerationNotifier, NullNotifier
from .registry import (
    SiteExistsError,
    SiteFrozenError,
    SiteNotFoundError,
    SiteOwnershipError,
    SiteRecord,
    SiteRegistry,
    SiteStatus,
)


def _default_html(name: str) -> str:
    return textwrap.dedent(
        f"""
        <!doctype html>
        <html lang=\"ru\">
        <head>
            <meta charset=\"utf-8\">
            <title>{name}</title>
            <link rel=\"stylesheet\" href=\"index.css\">
        </head>
        <body>
            <h1>Сайт {name}</h1>
            <p>Ваш сайт создан и ожидает модерации.</p>
            <script src=\"index.js\"></script>
        </body>
        </html>
        """
    ).strip()


def _default_css() -> str:
    return "body { font-family: system-ui, sans-serif; padding: 2rem; }"


def _default_js() -> str:
    return "console.log('site ready');"


def _serialize(record: SiteRecord, *, include_tokens: bool = False):
    payload = record.to_dict(include_tokens=include_tokens)
    payload["status"] = SiteStatus(payload["status"]).value
    return payload


def create_api_blueprint(
    registry: SiteRegistry, notifier: ModerationNotifier | None = None
) -> Blueprint:
    bp = Blueprint("api", __name__, url_prefix="/api")
    notifier = notifier or NullNotifier()

    def json_error(message: str, status: HTTPStatus):
        response = jsonify({"error": message})
        response.status_code = status
        return response

    def require_admin():
        admin_token = current_app.config.get("ADMIN_TOKEN")
        supplied = request.headers.get("X-Admin-Token")
        if not admin_token or supplied != admin_token:
            return False
        return True

    def include_tokens(record: SiteRecord) -> bool:
        owner_token = request.headers.get("X-Owner-Token")
        admin = require_admin()
        return admin or (owner_token and owner_token == record.owner_token)

    @bp.get("/sites")
    def list_sites():
        records = [
            record.to_dict(include_tokens=False)
            for record in registry.list_sites().values()
        ]
        return jsonify({"sites": records})

    @bp.post("/sites")
    def create_site():
        data = request.get_json(force=True) or {}
        name = (data.get("name") or "").strip()
        owner_id = (data.get("owner_id") or "").strip()
        if not name:
            return json_error("Site name is required", HTTPStatus.BAD_REQUEST)
        if not owner_id:
            return json_error("Owner id is required", HTTPStatus.BAD_REQUEST)

        html = data.get("html") or _default_html(name)
        css = data.get("css") or _default_css()
        js = data.get("js") or _default_js()

        try:
            record = registry.create_site(
                name, owner_id=owner_id, html=html, css=css, js=js
            )
        except ValueError as exc:
            return json_error(str(exc), HTTPStatus.BAD_REQUEST)
        except SiteExistsError:
            return json_error("Site already registered", HTTPStatus.CONFLICT)

        response = jsonify(_serialize(record, include_tokens=True))
        response.status_code = HTTPStatus.CREATED
        notifier.site_pending(record)
        return response

    @bp.get("/sites/<name>")
    def get_site(name: str):
        record = registry.get(name)
        if not record:
            return json_error("Site not found", HTTPStatus.NOT_FOUND)
        return jsonify(_serialize(record, include_tokens=include_tokens(record)))

    @bp.put("/sites/<name>/content")
    def update_site(name: str):
        data = request.get_json(force=True) or {}
        owner_token = request.headers.get("X-Owner-Token")
        if not owner_token:
            return json_error("Missing owner token", HTTPStatus.UNAUTHORIZED)

        html = data.get("html")
        css = data.get("css")
        js = data.get("js")
        if html is None or css is None or js is None:
            return json_error("html, css and js fields are required", HTTPStatus.BAD_REQUEST)

        try:
            record = registry.update_content(
                name, owner_token=owner_token, html=html, css=css, js=js
            )
        except SiteNotFoundError:
            return json_error("Site not found", HTTPStatus.NOT_FOUND)
        except SiteOwnershipError:
            return json_error("Owner token invalid", HTTPStatus.FORBIDDEN)
        except SiteFrozenError:
            return json_error("Site is frozen", HTTPStatus.FORBIDDEN)

        notifier.site_pending(record)
        return jsonify(_serialize(record, include_tokens=True))

    @bp.post("/sites/<name>/approve")
    def approve_site(name: str):
        if not require_admin():
            return json_error("Admin token required", HTTPStatus.FORBIDDEN)
        try:
            record = registry.approve(name)
        except SiteNotFoundError:
            return json_error("Site not found", HTTPStatus.NOT_FOUND)
        notifier.site_approved(record)
        return jsonify(_serialize(record, include_tokens=False))

    @bp.post("/sites/<name>/reject")
    def reject_site(name: str):
        if not require_admin():
            return json_error("Admin token required", HTTPStatus.FORBIDDEN)
        try:
            record = registry.reject(name)
        except SiteNotFoundError:
            return json_error("Site not found", HTTPStatus.NOT_FOUND)
        notifier.site_rejected(record)
        return jsonify(_serialize(record, include_tokens=False))

    return bp


__all__ = ["create_api_blueprint"]
