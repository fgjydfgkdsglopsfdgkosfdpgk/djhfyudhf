"""Support message persistence for the management UI."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class SupportMessage:
    """A message sent by a user to support."""

    id: str
    account_id: str
    subject: str
    message: str
    created_at: float

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "subject": self.subject,
            "message": self.message,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "SupportMessage":
        return cls(
            id=data["id"],
            account_id=data["account_id"],
            subject=data.get("subject", ""),
            message=data.get("message", ""),
            created_at=float(data.get("created_at", 0.0)),
        )


class SupportStore:
    """Persist and retrieve support messages."""

    def __init__(self, root: Path):
        self.root = root
        self._store_path = self.root / "_support.json"
        self._messages: List[SupportMessage] = []
        self._load()

    def _load(self) -> None:
        if not self._store_path.exists():
            return
        data = json.loads(self._store_path.read_text(encoding="utf-8"))
        for payload in data:
            self._messages.append(SupportMessage.from_dict(payload))

    def _dump(self) -> None:
        tmp_path = self._store_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps([msg.to_dict() for msg in self._messages], indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self._store_path)

    def add(self, account_id: str, subject: str, message: str) -> SupportMessage:
        identifier = f"msg-{int(time.time() * 1000)}-{len(self._messages) + 1}"
        entry = SupportMessage(
            id=identifier,
            account_id=account_id,
            subject=subject.strip() or "Без темы",
            message=message.strip(),
            created_at=time.time(),
        )
        self._messages.append(entry)
        self._dump()
        return entry

    def list_messages(self) -> List[SupportMessage]:
        return list(self._messages)


__all__ = ["SupportMessage", "SupportStore"]
