"""Account storage helpers for the management UI."""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class Account:
    """A registered owner account."""

    id: str
    display_name: str
    email: str
    token: str
    frozen: bool = False

    def to_dict(self, include_token: bool = False) -> Dict[str, str]:
        payload = {
            "id": self.id,
            "display_name": self.display_name,
            "email": self.email,
            "frozen": self.frozen,
        }
        if include_token:
            payload["token"] = self.token
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "Account":
        return cls(
            id=data["id"],
            display_name=data.get("display_name", ""),
            email=data.get("email", ""),
            token=data["token"],
            frozen=bool(data.get("frozen", False)),
        )


class AccountStore:
    """Persistent registry for owner accounts."""

    def __init__(self, root: Path):
        self.root = root
        self._store_path = self.root / "_accounts.json"
        self._accounts: Dict[str, Account] = {}
        self._by_token: Dict[str, Account] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not self._store_path.exists():
            return
        data = json.loads(self._store_path.read_text(encoding="utf-8"))
        for account_id, payload in data.items():
            account = Account.from_dict(payload)
            self._accounts[account_id] = account
            self._by_token[account.token] = account

    def _dump(self) -> None:
        data = {
            account_id: account.to_dict(include_token=True)
            for account_id, account in self._accounts.items()
        }
        tmp_path = self._store_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(self._store_path)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _generate_id(self) -> str:
        while True:
            candidate = secrets.token_urlsafe(8)
            if candidate not in self._accounts:
                return candidate

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def create(self, display_name: str, email: str) -> Account:
        if not email:
            raise ValueError("Email is required")
        account_id = self._generate_id()
        token = secrets.token_urlsafe(24)
        account = Account(
            id=account_id,
            display_name=display_name.strip() or "Без имени",
            email=email.strip(),
            token=token,
        )
        self._accounts[account_id] = account
        self._by_token[token] = account
        self._dump()
        return account

    def get(self, account_id: Optional[str]) -> Optional[Account]:
        if not account_id:
            return None
        return self._accounts.get(account_id)

    def get_by_token(self, token: str) -> Optional[Account]:
        return self._by_token.get(token)

    def update(self, account_id: str, *, display_name: str, email: str) -> Account:
        account = self._accounts.get(account_id)
        if not account:
            raise KeyError(account_id)
        account.display_name = display_name.strip() or account.display_name
        account.email = email.strip() or account.email
        self._dump()
        return account

    def freeze(self, account_id: str) -> Account:
        account = self._accounts.get(account_id)
        if not account:
            raise KeyError(account_id)
        if not account.frozen:
            account.frozen = True
            self._dump()
        return account

    def unfreeze(self, account_id: str) -> Account:
        account = self._accounts.get(account_id)
        if not account:
            raise KeyError(account_id)
        if account.frozen:
            account.frozen = False
            self._dump()
        return account

    def list_accounts(self) -> Dict[str, Account]:
        return dict(self._accounts)


__all__ = ["Account", "AccountStore"]
