"""Telegram moderation bot integration."""
from __future__ import annotations

import asyncio
from collections import deque
import logging
from threading import Lock, Thread
from typing import Deque, Dict, Tuple
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .accounts import AccountStore
from .notifications import ModerationNotifier
from .registry import SiteRecord, SiteRegistry, SiteVersionStatus


LOGGER = logging.getLogger(__name__)


class TelegramModerationBot(ModerationNotifier):
    """Admin moderation helper that works via Telegram."""

    def __init__(
        self,
        *,
        token: str,
        registry: SiteRegistry,
        accounts: AccountStore | None = None,
        admin_chat_id: int,
        base_url: str,
        poll_interval: float = 5.0,
    ) -> None:
        self.registry = registry
        self.accounts = accounts
        self.admin_chat_id = admin_chat_id
        self.base_url = base_url.rstrip("/")
        self.poll_interval = poll_interval
        self._application = Application.builder().token(token).build()
        self._pending_buffer: Deque[SiteRecord] = deque()
        self._status_buffer: Deque[Tuple[str, SiteRecord]] = deque()
        self._buffer_lock = Lock()
        self._seen_tokens: Dict[str, str] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

        self._install_handlers()

    # ------------------------------------------------------------------
    # ModerationNotifier implementation
    # ------------------------------------------------------------------
    def site_pending(self, record: SiteRecord) -> None:
        with self._buffer_lock:
            self._pending_buffer.append(record)
        self._trigger_flush()

    def site_approved(self, record: SiteRecord) -> None:
        with self._buffer_lock:
            self._status_buffer.append(("approved", record))
            self._seen_tokens.pop(record.name, None)
        self._trigger_flush()

    def site_rejected(self, record: SiteRecord) -> None:
        with self._buffer_lock:
            self._status_buffer.append(("rejected", record))
            self._seen_tokens.pop(record.name, None)
        self._trigger_flush()

    # ------------------------------------------------------------------
    # Telegram application lifecycle
    # ------------------------------------------------------------------
    def _install_handlers(self) -> None:
        self._application.add_handler(CommandHandler("start", self._cmd_start))
        self._application.add_handler(CommandHandler("pending", self._cmd_pending))
        self._application.add_handler(CallbackQueryHandler(self._handle_callback))
        job_queue = self._application.job_queue
        if job_queue is not None:
            job_queue.run_repeating(
                self._flush_buffers_job,
                interval=self.poll_interval,
                name="moderation-flush",
            )
        else:
            LOGGER.warning(
                "Job queue unavailable; moderation bot will flush notifications on-demand."
            )
        self._application.post_init = self._post_init

    async def _post_init(self, application: Application) -> None:
        # Discover pending sites that existed before the bot started.
        self._loop = asyncio.get_running_loop()
        for record in self.registry.list_sites().values():
            if record.pending_version():
                self.site_pending(record)
        await self._flush_buffers_job(None)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run_polling(self) -> None:
        """Start the bot and block the current thread."""

        LOGGER.info("Starting Telegram moderation bot")
        try:
            self._application.run_polling(
                close_loop=True,
                stop_signals=None,
                allowed_updates=Update.ALL_TYPES,
            )
        finally:
            self._loop = None

    def start_background(self) -> Thread:
        """Start the bot in a background daemon thread."""

        thread = Thread(target=self.run_polling, daemon=True)
        thread.start()
        return thread

    # ------------------------------------------------------------------
    # Telegram command handlers
    # ------------------------------------------------------------------
    def _authorized(self, update: Update) -> bool:
        chat = update.effective_chat
        return bool(chat and chat.id == self.admin_chat_id)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            if update.effective_message:
                await update.effective_message.reply_text("Доступ запрещён.")
            return

        if update.effective_message:
            await update.effective_message.reply_text(
                "Бот модерации активен. Используйте /pending, чтобы получить ссылки на ожидающие сайты."
            )

    async def _cmd_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._authorized(update):
            if update.effective_message:
                await update.effective_message.reply_text("Доступ запрещён.")
            return

        pending = [
            record for record in self.registry.list_sites().values() if record.pending_version()
        ]

        if not pending:
            if update.effective_message:
                await update.effective_message.reply_text("В ожидании нет сайтов.")
            return

        for record in pending:
            await self._send_pending(record)

    # ------------------------------------------------------------------
    # Callback handler
    # ------------------------------------------------------------------
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return

        if query.message and query.message.chat_id != self.admin_chat_id:
            await query.answer("Недостаточно прав", show_alert=True)
            return

        action, _, site = query.data.partition(":")

        try:
            if action == "approve":
                record = self.registry.approve(site)
                await query.answer("Сайт принят")
                await query.edit_message_text(self._format_status_text("approved", record))
                self.site_approved(record)
            elif action == "reject":
                record = self.registry.reject(site)
                await query.answer("Сайт отклонён")
                await query.edit_message_text(self._format_status_text("rejected", record))
                self.site_rejected(record)
                if self.accounts and record.approved_versions():
                    try:
                        self.accounts.freeze(record.owner_id)
                    except KeyError:  # pragma: no cover - defensive
                        LOGGER.warning("Не удалось заморозить аккаунт %s", record.owner_id)
            else:
                await query.answer("Неизвестное действие", show_alert=True)
        except Exception as exc:  # pragma: no cover - defensive fallback
            LOGGER.exception("Failed to process callback: %s", exc)
            await query.answer("Ошибка", show_alert=True)

    # ------------------------------------------------------------------
    # Buffer flushing
    # ------------------------------------------------------------------
    def _drain_buffers(self) -> Tuple[list[SiteRecord], list[Tuple[str, SiteRecord]]]:
        pending: list[SiteRecord] = []
        status: list[Tuple[str, SiteRecord]] = []
        with self._buffer_lock:
            while self._pending_buffer:
                pending.append(self._pending_buffer.popleft())
            while self._status_buffer:
                status.append(self._status_buffer.popleft())
        return pending, status

    async def _flush_buffers_job(self, context: ContextTypes.DEFAULT_TYPE | None) -> None:
        pending, statuses = self._drain_buffers()
        for record in pending:
            await self._send_pending(record)
        for status, record in statuses:
            await self._send_status(status, record)

    def _trigger_flush(self) -> None:
        loop = self._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._flush_buffers_job(None),
                loop,
            )

    # ------------------------------------------------------------------
    # Message helpers
    # ------------------------------------------------------------------
    def _preview_url(self, record: SiteRecord) -> str:
        base = self.base_url
        path = "" if record.name == "_" else f"/{quote(record.name)}"
        pending = record.pending_version()
        token = pending.preview_token if pending else ""
        if not token:
            return f"{base}{path}/"
        return f"{base}{path}/?preview_token={token}"

    def _format_pending_text(self, record: SiteRecord) -> str:
        preview_url = self._preview_url(record)
        return (
            f"Сайт «{record.name}» ожидает модерации.\n"
            f"Владелец: {record.owner_id}\n"
            f"Предпросмотр: {preview_url}"
        )

    def _format_status_text(self, status: str, record: SiteRecord) -> str:
        if status == "approved":
            return f"Сайт «{record.name}» опубликован."
        if status == "rejected":
            return f"Сайт «{record.name}» отклонён."
        return f"Статус сайта «{record.name}» обновлён."

    async def _send_pending(self, record: SiteRecord) -> None:
        pending = record.pending_version()
        if not pending or pending.status != SiteVersionStatus.PENDING:
            return

        previous = self._seen_tokens.get(record.name)
        if previous == pending.preview_token:
            return
        self._seen_tokens[record.name] = pending.preview_token

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Принять", callback_data=f"approve:{record.name}"),
                    InlineKeyboardButton("❌ Отклонить", callback_data=f"reject:{record.name}"),
                ]
            ]
        )

        await self._application.bot.send_message(
            chat_id=self.admin_chat_id,
            text=self._format_pending_text(record),
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

    async def _send_status(self, status: str, record: SiteRecord) -> None:
        await self._application.bot.send_message(
            chat_id=self.admin_chat_id,
            text=self._format_status_text(status, record),
        )


__all__ = ["TelegramModerationBot"]
