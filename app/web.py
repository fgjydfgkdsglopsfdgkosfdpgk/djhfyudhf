"""Minimal management UI for accounts and sites."""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from flask import (
    Blueprint,
    Response,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from .accounts import AccountStore
from .notifications import ModerationNotifier, NullNotifier
from .registry import SiteLifecycle, SiteRecord, SiteRegistry, SiteVersionStatus
from .support import SupportStore


def create_web_blueprint(
    registry: SiteRegistry,
    *,
    accounts: AccountStore,
    support: SupportStore,
    notifier: ModerationNotifier | None = None,
) -> Blueprint:
    bp = Blueprint("web", __name__, url_prefix="/ui")
    notifier = notifier or NullNotifier()

    def current_account():
        return getattr(g, "current_account", None)

    @bp.before_app_request
    def load_account():  # pragma: no cover - simple session helper
        account_id = session.get("account_id")
        account = accounts.get(account_id)
        g.current_account = account

    def require_login() -> Optional[Response]:
        account = current_account()
        if account is None:
            flash("Пожалуйста, войдите в систему.", "warning")
            return redirect(url_for("web.login"))
        return None

    def require_active_account() -> Optional[Response]:
        account = current_account()
        if account and account.frozen:
            flash("Аккаунт заморожен и не может управлять сайтами.", "danger")
            return redirect(url_for("web.dashboard"))
        return None

    @bp.route("/")
    def index():
        account = current_account()
        if account:
            return redirect(url_for("web.dashboard"))
        return render_template("home.html")

    @bp.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            display_name = (request.form.get("display_name") or "").strip()
            email = (request.form.get("email") or "").strip()
            if not email:
                flash("Введите адрес электронной почты", "danger")
                return render_template("register.html")
            account = accounts.create(display_name, email)
            session["account_id"] = account.id
            flash("Аккаунт создан. Сохраните ваш токен доступа!", "success")
            return render_template("register_success.html", account=account)
        return render_template("register.html")

    @bp.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            token = (request.form.get("token") or "").strip()
            account = accounts.get_by_token(token)
            if not account:
                flash("Неверный токен", "danger")
                return render_template("login.html")
            session["account_id"] = account.id
            flash("Вы успешно вошли.", "success")
            return redirect(url_for("web.dashboard"))
        return render_template("login.html")

    @bp.route("/logout")
    def logout():
        session.pop("account_id", None)
        flash("Вы вышли из аккаунта.", "info")
        return redirect(url_for("web.index"))

    @bp.route("/dashboard")
    def dashboard():
        guard = require_login()
        if guard:
            return guard
        account = current_account()
        registry_sites = registry.list_sites()
        owned = [
            record
            for record in registry_sites.values()
            if record.owner_id == account.id
        ]
        return render_template(
            "dashboard.html",
            account=account,
            sites=owned,
            SiteLifecycle=SiteLifecycle,
        )

    @bp.route("/sites/new", methods=["GET", "POST"])
    def create_site():
        guard = require_login()
        if guard:
            return guard
        frozen_guard = require_active_account()
        if frozen_guard:
            return frozen_guard
        account = current_account()
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            html = request.form.get("html") or ""
            css = request.form.get("css") or ""
            js = request.form.get("js") or ""
            if not name:
                flash("Введите имя поддомена", "danger")
                return render_template("create_site.html")
            try:
                record = registry.create_site(
                    name,
                    owner_id=account.id,
                    html=html,
                    css=css,
                    js=js,
                )
            except ValueError as exc:
                flash(str(exc), "danger")
                return render_template("create_site.html")
            except Exception:
                flash("Не удалось создать сайт", "danger")
                return render_template("create_site.html")
            notifier.site_pending(record)
            flash("Сайт создан и отправлен на модерацию", "success")
            return render_template(
                "site_created.html",
                record=record,
                pending_version=record.pending_version(),
            )
        return render_template("create_site.html")

    def _site_or_redirect(name: str):
        guard = require_login()
        if guard:
            return None, guard
        account = current_account()
        record = registry.get(name)
        if not record or record.owner_id != account.id:
            flash("Сайт не найден", "danger")
            return None, redirect(url_for("web.dashboard"))
        return record, None

    @bp.route("/sites/<name>", methods=["GET", "POST"])
    def site_detail(name: str):
        record, guard = _site_or_redirect(name)
        if guard:
            return guard
        if record is None:
            return guard

        def _refresh_contents(current_record: SiteRecord):
            active = None
            if current_record.active_version:
                active = registry.read_content(name, version_id=current_record.active_version)
            pending_version = current_record.pending_version()
            pending_content = (
                registry.read_content(name, version_id=pending_version.version_id)
                if pending_version
                else None
            )
            return active, pending_version, pending_content

        active_content, pending_version, pending_content = _refresh_contents(record)

        if request.method == "POST":
            frozen_guard = require_active_account()
            if frozen_guard:
                return frozen_guard
            action = request.form.get("action") or ""
            try:
                if action == "update":
                    html = request.form.get("html") or (
                        (pending_content or active_content or {}).get("html", "")
                    )
                    css = request.form.get("css") or (
                        (pending_content or active_content or {}).get("css", "")
                    )
                    js = request.form.get("js") or (
                        (pending_content or active_content or {}).get("js", "")
                    )
                    record = registry.update_content(
                        name,
                        owner_token=record.owner_token,
                        html=html,
                        css=css,
                        js=js,
                    )
                    notifier.site_pending(record)
                    flash("Контент обновлён и отправлен на модерацию", "success")
                elif action == "set_active":
                    version_id = (request.form.get("version_id") or "").strip()
                    if not version_id:
                        raise ValueError("Укажите версию для активации")
                    record = registry.set_active_version(
                        name,
                        owner_token=record.owner_token,
                        version_id=version_id,
                    )
                    flash("Версия активирована", "success")
                elif action == "delete_version":
                    version_id = (request.form.get("version_id") or "").strip()
                    if not version_id:
                        raise ValueError("Укажите версию для удаления")
                    record = registry.delete_version(
                        name,
                        owner_token=record.owner_token,
                        version_id=version_id,
                    )
                    flash("Версия удалена", "info")
                elif action == "delete_site":
                    registry.delete_site(name, owner_token=record.owner_token, purge=True)
                    flash("Сайт удалён", "info")
                    return redirect(url_for("web.dashboard"))
                else:
                    flash("Неизвестное действие", "danger")
            except Exception as exc:
                flash(str(exc), "danger")
            active_content, pending_version, pending_content = _refresh_contents(record)

        versions = sorted(record.versions.values(), key=lambda v: v.created_at)
        return render_template(
            "site_detail.html",
            record=record,
            lifecycle=record.lifecycle,
            active_content=active_content,
            pending_version=pending_version,
            pending_content=pending_content,
            versions=versions,
            SiteVersionStatus=SiteVersionStatus,
            SiteLifecycle=SiteLifecycle,
        )

    @bp.route("/support", methods=["GET", "POST"])
    def support_form():
        guard = require_login()
        if guard:
            return guard
        account = current_account()
        if request.method == "POST":
            subject = request.form.get("subject") or ""
            message = request.form.get("message") or ""
            if not message.strip():
                flash("Опишите вашу проблему", "danger")
                return render_template("support.html")
            support.add(account.id, subject, message)
            flash("Сообщение отправлено", "success")
            return redirect(url_for("web.dashboard"))
        return render_template("support.html")

    @bp.route("/settings", methods=["GET", "POST"])
    def settings():
        guard = require_login()
        if guard:
            return guard
        account = current_account()
        if request.method == "POST":
            display_name = request.form.get("display_name") or account.display_name
            email = request.form.get("email") or account.email
            accounts.update(account.id, display_name=display_name, email=email)
            flash("Настройки обновлены", "success")
            return redirect(url_for("web.settings"))
        return render_template("settings.html", account=account)

    @bp.route("/me")
    def profile():
        guard = require_login()
        if guard:
            return guard
        account = current_account()
        return render_template("profile.json.j2", account=account, asdict=asdict)

    return bp


__all__ = ["create_web_blueprint"]
