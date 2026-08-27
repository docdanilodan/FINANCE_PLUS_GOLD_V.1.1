from __future__ import annotations
import os
from typing import Any, Dict, Iterable, Optional
import requests

DEFAULT_BASE_ID = "appoNJtS64JIcZUhT"
TABLES = {
    "clienti": "tbltOh4J8m5VHoNOF",
    "pratiche": "tbl0qFi8aXz68jL1v",
    "documenti": "tblWxkIGieQuW8Cuo",
    "email": "tblmOCSQfwc3VItpm",
    "analisi": "tblACV72ySC38jmvO",
}

class AirtableGold:
    def __init__(self, token: Optional[str] = None, base_id: Optional[str] = None):
        self.token = token or os.getenv("AIRTABLE_TOKEN", "")
        self.base_id = base_id or os.getenv("AIRTABLE_BASE_ID", DEFAULT_BASE_ID)
        if not self.token:
            raise RuntimeError("AIRTABLE_TOKEN non configurato")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})

    def _url(self, table_id: str) -> str:
        return f"https://api.airtable.com/v0/{self.base_id}/{table_id}"

    def list_records(self, table: str, max_records: int = 100) -> list[dict]:
        table_id = TABLES[table]
        out: list[dict] = []
        params: Dict[str, Any] = {"pageSize": min(max_records, 100)}
        while len(out) < max_records:
            r = self.session.get(self._url(table_id), params=params, timeout=30)
            r.raise_for_status(); data = r.json(); out.extend(data.get("records", []))
            if not data.get("offset") or len(out) >= max_records: break
            params["offset"] = data["offset"]
        return out[:max_records]

    def get_record(self, table: str, record_id: str) -> dict:
        r = self.session.get(f"{self._url(TABLES[table])}/{record_id}", timeout=30)
        r.raise_for_status()
        return r.json()

    def get_records_by_ids(self, table: str, record_ids: Iterable[str], max_records: int = 100) -> list[dict]:
        out: list[dict] = []
        for record_id in list(record_ids)[:max_records]:
            try:
                out.append(self.get_record(table, record_id))
            except requests.HTTPError:
                continue
        return out

    def create_record(self, table: str, fields: Dict[str, Any]) -> dict:
        r = self.session.post(self._url(TABLES[table]), json={"fields": fields, "typecast": True}, timeout=30)
        r.raise_for_status(); return r.json()

    def update_record(self, table: str, record_id: str, fields: Dict[str, Any]) -> dict:
        r = self.session.patch(f"{self._url(TABLES[table])}/{record_id}", json={"fields": fields, "typecast": True}, timeout=30)
        r.raise_for_status(); return r.json()

    def upsert_by_field(self, table: str, field_name: str, value: str, fields: Dict[str, Any]) -> dict:
        safe = value.replace("'", "\\'")
        params = {"filterByFormula": f"{{{field_name}}}='{safe}'", "maxRecords": 1}
        r = self.session.get(self._url(TABLES[table]), params=params, timeout=30)
        r.raise_for_status(); recs = r.json().get("records", [])
        if recs:
            return self.update_record(table, recs[0]["id"], fields)
        return self.create_record(table, fields)
