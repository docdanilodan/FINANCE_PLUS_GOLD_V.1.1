from __future__ import annotations

import os
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

    def payloads(self, webhook_id: str, cursor: int | None = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        if cursor is not None:
            params["cursor"] = cursor
        response = self.session.get(
            f"{self.base_url}/{webhook_id}/payloads",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def refresh(self, webhook_id: str) -> Dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/{webhook_id}/refresh",
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def delete(self, webhook_id: str) -> None:
        response = self.session.delete(f"{self.base_url}/{webhook_id}", timeout=30)
        response.raise_for_status()
