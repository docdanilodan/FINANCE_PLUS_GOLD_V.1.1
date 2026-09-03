from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timezone
from typing import Any, Iterable

import requests


class OpenAIUsageClient:
    """Read-only organization cost client for the OpenAI Administration API."""

    def __init__(
        self,
        admin_key: str | None = None,
        base_url: str | None = None,
        session: requests.Session | None = None,
    ):
        self.admin_key = admin_key or os.getenv("OPENAI_ADMIN_KEY", "")
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        if not self.admin_key:
            raise RuntimeError("OPENAI_ADMIN_KEY non configurata")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.admin_key}",
                "Content-Type": "application/json",
            }
        )

    @staticmethod
    def _unix_start(value: date | datetime | int) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, datetime):
            moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        else:
            moment = datetime.combine(value, time.min, tzinfo=timezone.utc)
        return int(moment.timestamp())

    def costs(
        self,
        *,
        start: date | datetime | int,
        end: date | datetime | int | None = None,
        api_key_ids: Iterable[str] | None = None,
        max_pages: int = 20,
    ) -> list[dict[str, Any]]:
        start_time = self._unix_start(start)
        end_time = self._unix_start(end) if end is not None else None
        if end_time is not None and end_time <= start_time:
            raise ValueError("L'intervallo costi OpenAI non è valido")

        params: list[tuple[str, Any]] = [
            ("start_time", start_time),
            ("bucket_width", "1d"),
            ("limit", 180),
            ("group_by", "api_key_id"),
            ("group_by", "line_item"),
        ]
        if end_time is not None:
            params.append(("end_time", end_time))
        for key_id in api_key_ids or []:
            if str(key_id).strip():
                params.append(("api_key_ids", str(key_id).strip()))

        buckets: list[dict[str, Any]] = []
        page: str | None = None
        for _ in range(max_pages):
            request_params = list(params)
            if page:
                request_params.append(("page", page))
            response = self.session.get(
                f"{self.base_url}/organization/costs",
                params=request_params,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            buckets.extend(payload.get("data", []) or [])
            page = payload.get("next_page")
            if not payload.get("has_more") or not page:
                break
        else:
            raise RuntimeError("Paginazione costi OpenAI oltre il limite di sicurezza")
        return buckets


def load_key_labels(raw: str | None = None) -> dict[str, str]:
    """Map non-secret API key IDs to FinancePlus module labels."""
    source = raw if raw is not None else os.getenv("FINANCEPLUS_OPENAI_KEY_LABELS_JSON", "{}")
    try:
        parsed = json.loads(source or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        str(key).strip(): str(value).strip()[:80]
        for key, value in parsed.items()
        if str(key).strip() and str(value).strip()
    }


def flatten_costs(
    buckets: Iterable[dict[str, Any]],
    key_labels: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    labels = key_labels or {}
    rows: list[dict[str, Any]] = []
    for bucket in buckets:
        start_time = int(bucket.get("start_time") or 0)
        day = datetime.fromtimestamp(start_time, tz=timezone.utc).date().isoformat() if start_time else ""
        for result in bucket.get("results", []) or []:
            amount = result.get("amount") or {}
            key_id = str(result.get("api_key_id") or "non attribuita")
            rows.append(
                {
                    "Data": day,
                    "Modulo": labels.get(key_id, "Non mappato"),
                    "API key ID": key_id,
                    "Voce": str(result.get("line_item") or "Totale"),
                    "Importo": float(amount.get("value") or 0),
                    "Valuta": str(amount.get("currency") or "usd").upper(),
                }
            )
    return rows
