from __future__ import annotations

import os
import re
from typing import Any, Dict

import requests


class AirtableWebhookClient:
    """Thin client for Airtable's Webhooks API.

    The webhook specification is passed through unchanged so FinancePlus can
    adopt new Airtable webhook filters without changing this client.
    """

    def __init__(self, token: str | None = None, base_id: str | None = None):
        self.token = token or os.getenv("AIRTABLE_TOKEN", "")
        self.base_id = base_id or os.getenv("AIRTABLE_BASE_ID", "")
        if not self.token or not self.base_id:
            raise RuntimeError("AIRTABLE_TOKEN / AIRTABLE_BASE_ID non configurati")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        })

    @property
    def base_url(self) -> str:
        return f"https://api.airtable.com/v0/bases/{self.base_id}/webhooks"

    @staticmethod
    def _webhook_id(value: str) -> str:
        webhook_id = str(value or "").strip()
        if not re.fullmatch(r"ach[A-Za-z0-9]{14}", webhook_id):
            raise ValueError("Airtable webhook ID non valido")
        return webhook_id

    def create(self, *, notification_url: str, specification: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.post(
            self.base_url,
            json={
                "notificationUrl": notification_url,
                "specification": specification,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def list(self) -> Dict[str, Any]:
        response = self.session.get(self.base_url, timeout=30)
        response.raise_for_status()
        return response.json()

    def payloads(
        self,
        webhook_id: str,
        cursor: int | None = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        webhook_id = self._webhook_id(webhook_id)
        params: Dict[str, Any] = {}
        if cursor is not None:
            if cursor < 1:
                raise ValueError("Il cursore Airtable deve essere positivo")
            params["cursor"] = cursor
        params["limit"] = max(1, min(int(limit), 50))
        response = self.session.get(
            f"{self.base_url}/{webhook_id}/payloads",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def drain_payloads(
        self,
        webhook_id: str,
        *,
        cursor: int | None = None,
        max_pages: int = 20,
    ) -> Dict[str, Any]:
        """Read all currently queued payloads and return the durable next cursor."""
        webhook_id = self._webhook_id(webhook_id)
        collected: list[dict[str, Any]] = []
        next_cursor = cursor
        for _ in range(max_pages):
            page = self.payloads(webhook_id, cursor=next_cursor, limit=50)
            collected.extend(page.get("payloads", []) or [])
            next_cursor = page.get("cursor", next_cursor)
            if not page.get("mightHaveMore"):
                return {"payloads": collected, "cursor": next_cursor}
        raise RuntimeError("Coda webhook Airtable oltre il limite di sicurezza")

    def refresh(self, webhook_id: str) -> Dict[str, Any]:
        webhook_id = self._webhook_id(webhook_id)
        response = self.session.post(
            f"{self.base_url}/{webhook_id}/refresh",
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def enable_notifications(self, webhook_id: str, *, enable: bool = True) -> Dict[str, Any]:
        webhook_id = self._webhook_id(webhook_id)
        response = self.session.post(
            f"{self.base_url}/{webhook_id}/enableNotifications",
            json={"enable": bool(enable)},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def delete(self, webhook_id: str) -> None:
        webhook_id = self._webhook_id(webhook_id)
        response = self.session.delete(f"{self.base_url}/{webhook_id}", timeout=30)
        response.raise_for_status()
