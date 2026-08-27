from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import requests


class AirtableAPIError(RuntimeError):
    pass


@dataclass
class AirtableClient:
    token: str
    base_id: str
    timeout: int = 30

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _url(self, table: str) -> str:
        return f"https://api.airtable.com/v0/{self.base_id}/{quote(table, safe='')}"

    def list_records(
        self,
        table: str,
        *,
        fields: Optional[Iterable[str]] = None,
        view: Optional[str] = None,
        max_records: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"pageSize": 100}
        if view:
            params["view"] = view
        if fields:
            params["fields[]"] = list(fields)

        records: List[Dict[str, Any]] = []
        offset: Optional[str] = None

        while True:
            if offset:
                params["offset"] = offset
            response = requests.get(
                self._url(table), headers=self.headers, params=params, timeout=self.timeout
            )
            if not response.ok:
                raise AirtableAPIError(
                    f"Airtable {response.status_code}: {response.text[:500]}"
                )
            payload = response.json()
            records.extend(payload.get("records", []))

            if max_records and len(records) >= max_records:
                return records[:max_records]

            offset = payload.get("offset")
            if not offset:
                break

        return records

    def create_record(self, table: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        response = requests.post(
            self._url(table),
            headers=self.headers,
            json={"fields": fields, "typecast": False},
            timeout=self.timeout,
        )
        if not response.ok:
            raise AirtableAPIError(
                f"Airtable {response.status_code}: {response.text[:500]}"
            )
        return response.json()

    def update_record(
        self, table: str, record_id: str, fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = requests.patch(
            f"{self._url(table)}/{record_id}",
            headers=self.headers,
            json={"fields": fields, "typecast": False},
            timeout=self.timeout,
        )
        if not response.ok:
            raise AirtableAPIError(
                f"Airtable {response.status_code}: {response.text[:500]}"
            )
        return response.json()
