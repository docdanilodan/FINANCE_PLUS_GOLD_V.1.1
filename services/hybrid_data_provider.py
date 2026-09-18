from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Iterable

from psycopg import connect
from psycopg.rows import dict_row

from services.airtable_adapter import AirtableGold


NEON_READ_TABLES = {"clienti", "pratiche", "documenti", "analisi"}


def _iso(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value or "")


def _record_id(table: str, raw_id: Any) -> str:
    return f"neon:{table}:{raw_id}"


def _neon_raw_id(record_id: str, table: str | None = None) -> int | None:
    parts = str(record_id or "").split(":")
    if len(parts) != 3 or parts[0] != "neon":
        return None
    if table and parts[1] != table:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


def is_neon_record(record_id: str) -> bool:
    return _neon_raw_id(record_id) is not None


class HybridDataProvider:
    """Neon-first read adapter with Airtable compatibility fallback.

    Phase-2 rules:
    - Neon becomes the read source only when a database URL is configured and
      the core clients table contains at least one row.
    - when Neon is empty/unavailable, Airtable remains the operational source;
    - unsupported tables continue through Airtable;
    - writes stay on Airtable and are blocked for Neon-sourced record IDs.

    This keeps the cutover reversible and prevents a configured-but-empty Neon
    database from blanking Cliente 360.
    """

    def __init__(
        self,
        *,
        database_url: str = "",
        airtable: AirtableGold | None = None,
        connect_fn=None,
    ):
        self.database_url = str(database_url or "").strip()
        self.airtable = airtable
        self._connect_fn = connect_fn or connect
        self._read_source: str | None = None
        self._neon_error = ""

    def __bool__(self) -> bool:
        return self.read_source != "none"

    @property
    def airtable_configured(self) -> bool:
        return self.airtable is not None

    @property
    def neon_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def neon_error(self) -> str:
        _ = self.read_source
        return self._neon_error

    @property
    def read_source(self) -> str:
        if self._read_source is None:
            self._read_source = self._resolve_read_source()
        return self._read_source

    @property
    def neon_core_ready(self) -> bool:
        return self.read_source == "neon"

    @property
    def source_label(self) -> str:
        return {
            "neon": "Neon PostgreSQL",
            "airtable": "Airtable fallback",
            "none": "Non configurato",
        }.get(self.read_source, self.read_source)

    def _resolve_read_source(self) -> str:
        if self.database_url:
            try:
                rows = self._fetchall(
                    "SELECT EXISTS(SELECT 1 FROM clients LIMIT 1) AS has_clients"
                )
                if rows and bool(rows[0].get("has_clients")):
                    return "neon"
            except Exception as exc:
                self._neon_error = f"{type(exc).__name__}: {exc}"[:500]
        if self.airtable is not None:
            return "airtable"
        return "none"

    def _fetchall(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        if not self.database_url:
            return []
        with self._connect_fn(
            self.database_url,
            connect_timeout=5,
            row_factory=dict_row,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def _neon_list_records(self, table: str, max_records: int) -> list[dict]:
        limit = max(1, min(int(max_records or 100), 5000))
        if table == "clienti":
            rows = self._fetchall(
                """
                SELECT id, legal_name, vat, tax_code, pec, rea,
                       registered_office, postal_code, city, province, ateco,
                       legal_form, administrator, share_capital, notes,
                       created_at, updated_at
                FROM clients
                ORDER BY legal_name, id
                LIMIT %s
                """,
                (limit,),
            )
            return [self._map_client(row) for row in rows]

        if table == "pratiche":
            rows = self._fetchall(
                """
                SELECT p.*, c.legal_name AS client_name
                FROM practices p
                JOIN clients c ON c.id = p.client_id
                ORDER BY p.id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [self._map_practice(row) for row in rows]

        if table == "documenti":
            rows = self._fetchall(
                """
                SELECT d.*, c.legal_name AS client_name, p.code AS practice_code
                FROM documents d
                LEFT JOIN clients c ON c.id = d.client_id
                LEFT JOIN practices p ON p.id = d.practice_id
                ORDER BY d.id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [self._map_document(row) for row in rows]

        if table == "analisi":
            rows = self._fetchall(
                """
                SELECT a.*, c.legal_name AS client_name, p.code AS practice_code
                FROM analyses a
                LEFT JOIN clients c ON c.id = a.client_id
                LEFT JOIN practices p ON p.id = a.practice_id
                ORDER BY a.id DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [self._map_analysis(row) for row in rows]

        return []

    def list_records(
        self,
        table: str,
        max_records: int = 100,
        formula: str | None = None,
    ) -> list[dict]:
        if self.read_source == "neon" and table in NEON_READ_TABLES:
            return self._neon_list_records(table, max_records)
        if self.airtable is not None:
            return self.airtable.list_records(
                table,
                max_records=max_records,
                formula=formula,
            )
        return []

    def get_record(self, table: str, record_id: str) -> dict:
        raw_id = _neon_raw_id(record_id, table)
        if self.read_source == "neon" and raw_id is not None and table in NEON_READ_TABLES:
            records = self._neon_records_by_ids(table, [raw_id], 1)
            if not records:
                raise KeyError(f"Record Neon non trovato: {record_id}")
            return records[0]
        if self.airtable is None:
            raise KeyError(f"Record non disponibile: {record_id}")
        return self.airtable.get_record(table, record_id)

    def get_records_by_ids(
        self,
        table: str,
        record_ids: Iterable[str],
        max_records: int = 100,
    ) -> list[dict]:
        ids = list(record_ids or [])[:max_records]
        neon_ids = [
            raw
            for raw in (_neon_raw_id(record_id, table) for record_id in ids)
            if raw is not None
        ]
        if self.read_source == "neon" and neon_ids and table in NEON_READ_TABLES:
            return self._neon_records_by_ids(table, neon_ids, max_records)
        if self.airtable is None:
            return []
        return self.airtable.get_records_by_ids(table, ids, max_records=max_records)

    def list_related_records(
        self,
        table: str,
        client_record_id: str,
        max_records: int = 1000,
    ) -> list[dict]:
        client_id = _neon_raw_id(client_record_id, "clienti")
        if self.read_source != "neon" or client_id is None:
            return []

        limit = max(1, min(int(max_records or 1000), 5000))
        if table == "pratiche":
            rows = self._fetchall(
                """
                SELECT p.*, c.legal_name AS client_name
                FROM practices p
                JOIN clients c ON c.id = p.client_id
                WHERE p.client_id = %s
                ORDER BY p.id DESC
                LIMIT %s
                """,
                (client_id, limit),
            )
            return [self._map_practice(row) for row in rows]

        if table == "documenti":
            rows = self._fetchall(
                """
                SELECT d.*, c.legal_name AS client_name, p.code AS practice_code
                FROM documents d
                LEFT JOIN clients c ON c.id = d.client_id
                LEFT JOIN practices p ON p.id = d.practice_id
                WHERE d.client_id = %s
                ORDER BY d.id DESC
                LIMIT %s
                """,
                (client_id, limit),
            )
            return [self._map_document(row) for row in rows]

        if table == "analisi":
            rows = self._fetchall(
                """
                SELECT a.*, c.legal_name AS client_name, p.code AS practice_code
                FROM analyses a
                LEFT JOIN clients c ON c.id = a.client_id
                LEFT JOIN practices p ON p.id = a.practice_id
                WHERE a.client_id = %s
                ORDER BY a.id DESC
                LIMIT %s
                """,
                (client_id, limit),
            )
            return [self._map_analysis(row) for row in rows]

        if table == "email" and self.airtable is not None:
            client = self.get_record("clienti", client_record_id)
            client_name = str(client.get("fields", {}).get("Cliente", "")).strip().casefold()
            if not client_name:
                return []
            records = self.airtable.list_records("email", max_records=limit)
            return [
                record
                for record in records
                if str(record.get("fields", {}).get("Cliente", "")).strip().casefold()
                == client_name
            ][:limit]

        return []

    def _neon_records_by_ids(
        self,
        table: str,
        raw_ids: Iterable[int],
        max_records: int,
    ) -> list[dict]:
        wanted = [int(value) for value in raw_ids][:max_records]
        if not wanted:
            return []
        all_records = self._neon_list_records(table, max_records=5000)
        wanted_set = set(wanted)
        return [
            record
            for record in all_records
            if (_neon_raw_id(record.get("id", ""), table) in wanted_set)
        ][:max_records]

    def create_record(self, table: str, fields: dict) -> dict:
        if self.airtable is None:
            raise RuntimeError(
                "Scrittura non disponibile: la fase read-shadow non scrive direttamente su Neon."
            )
        if self._contains_neon_id(fields):
            raise RuntimeError(
                "Scrittura bloccata: il record Cliente 360 proviene da Neon. "
                "La sincronizzazione write-through verra abilitata solo dopo migrazione controllata."
            )
        return self.airtable.create_record(table, fields)

    def update_record(self, table: str, record_id: str, fields: dict) -> dict:
        if is_neon_record(record_id):
            raise RuntimeError(
                "Scrittura bloccata sul record Neon durante la fase read-shadow."
            )
        if self.airtable is None:
            raise RuntimeError("Airtable non configurato per la scrittura di compatibilita.")
        return self.airtable.update_record(table, record_id, fields)

    def find_one(self, table: str, field_name: str, value: str) -> dict | None:
        if self.read_source == "neon" and table in NEON_READ_TABLES:
            for record in self.list_records(table, max_records=5000):
                if str(record.get("fields", {}).get(field_name, "")) == str(value):
                    return record
            return None
        return self.airtable.find_one(table, field_name, value) if self.airtable else None

    def upsert_by_field(
        self,
        table: str,
        field_name: str,
        value: str,
        fields: dict,
    ) -> dict:
        if self.airtable is None:
            raise RuntimeError("Airtable non configurato per l'upsert di compatibilita.")
        return self.airtable.upsert_by_field(table, field_name, value, fields)

    @staticmethod
    def _contains_neon_id(value: Any) -> bool:
        if isinstance(value, str):
            return value.startswith("neon:")
        if isinstance(value, dict):
            return any(HybridDataProvider._contains_neon_id(v) for v in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(HybridDataProvider._contains_neon_id(v) for v in value)
        return False

    @staticmethod
    def _map_client(row: dict) -> dict:
        fields = {
            "Cliente": row.get("legal_name", ""),
            "Partita IVA": row.get("vat", ""),
            "Codice Fiscale": row.get("tax_code", ""),
            "PEC": row.get("pec", ""),
            "REA": row.get("rea", ""),
            "Sede legale": row.get("registered_office", ""),
            "CAP": row.get("postal_code", ""),
            "Comune": row.get("city", ""),
            "Provincia": row.get("province", ""),
            "ATECO": row.get("ateco", ""),
            "Forma giuridica": row.get("legal_form", ""),
            "Rappresentante/Amministratore": row.get("administrator", ""),
            "Capitale sociale": row.get("share_capital"),
            "Note": row.get("notes", ""),
            "Origine dati": "Neon PostgreSQL",
        }
        return {"id": _record_id("clienti", row["id"]), "fields": fields}

    @staticmethod
    def _map_practice(row: dict) -> dict:
        fields = {
            "Pratica ID": row.get("code", ""),
            "Cliente": row.get("client_name", ""),
            "Tipo Pratica": row.get("practice_type", ""),
            "Istituto": row.get("institution", ""),
            "Importo Richiesto": row.get("requested_amount"),
            "Stato": row.get("status", ""),
            "Priorit\u00e0": row.get("priority", ""),
            "Responsabile pratica": row.get("owner", ""),
            "Prossima azione": row.get("next_action", ""),
            "Scadenza prossima azione": _iso(row.get("next_action_due")),
            "Documenti mancanti": row.get("missing_documents", ""),
            "Stato documentazione": row.get("documentation_status", ""),
            "Alert e criticit\u00e0": row.get("alerts", ""),
            "Origine dati": "Neon PostgreSQL",
        }
        return {"id": _record_id("pratiche", row["id"]), "fields": fields}

    @staticmethod
    def _map_document(row: dict) -> dict:
        metadata = row.get("metadata_json") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        fields = {
            "Cliente": row.get("client_name", ""),
            "Pratica ID": row.get("practice_code", ""),
            "Documento": row.get("canonical_name") or row.get("original_name", ""),
            "Tipo Documento": row.get("category", ""),
            "Nome Originale": row.get("original_name", ""),
            "Nome Definitivo": row.get("canonical_name", ""),
            "SHA-256": row.get("sha256", ""),
            "URL Drive": row.get("storage_uri", ""),
            "Origine": row.get("source_channel", ""),
            "Message ID sorgente": row.get("source_message_id", ""),
            "Stato Verifica": row.get("verification_status", ""),
            "Data Documento": _iso(row.get("document_date")),
            "Esercizio": row.get("fiscal_year"),
            "Origine dati": "Neon PostgreSQL",
        }
        for key in (
            "Sensibilit\u00e0 dati",
            "Protezione Drive",
            "Policy elaborazione AI",
            "Caselle origine",
        ):
            if key in metadata:
                fields[key] = metadata[key]
        return {"id": _record_id("documenti", row["id"]), "fields": fields}

    @staticmethod
    def _map_analysis(row: dict) -> dict:
        result = row.get("result_json") or {}
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = {}
        metrics = result.get("metrics") if isinstance(result, dict) else {}
        metrics = metrics if isinstance(metrics, dict) else {}

        def pick(*keys):
            for key in keys:
                if isinstance(result, dict) and result.get(key) is not None:
                    return result.get(key)
                if metrics.get(key) is not None:
                    return metrics.get(key)
            return None

        fields = {
            "Data Analisi": _iso(row.get("created_at")),
            "Cliente": row.get("client_name", ""),
            "Pratica ID": row.get("practice_code", ""),
            "Tipo Analisi": row.get("analysis_type", ""),
            "Data Quality": row.get("data_quality"),
            "Score": row.get("score"),
            "Rating": row.get("rating", ""),
            "PD": row.get("pd_label", ""),
            "Ricavi": pick("revenue", "ricavi"),
            "EBITDA": pick("ebitda"),
            "PFN": pick("pfn"),
            "PFN EBITDA": pick("pfn_ebitda"),
            "DSCR": pick("dscr"),
            "Current Ratio": pick("current_ratio"),
            "Debt Equity": pick("debt_equity"),
            "Origine dati": "Neon PostgreSQL",
        }
        return {"id": _record_id("analisi", row["id"]), "fields": fields}
