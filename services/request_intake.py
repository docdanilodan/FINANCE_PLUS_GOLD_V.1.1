from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from services.airtable_adapter import AirtableGold
from services.client_practice_matcher import MatchResult, match_client_practice


ITALIAN_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}

DOCUMENT_PATTERNS = {
    "Visura camerale": ("visura", "visura camerale"),
    "Bilancio": ("bilancio", "bilanci"),
    "Situazione contabile": ("situazione contabile", "situazione economico patrimoniale"),
    "Centrale Rischi": ("centrale rischi", "cr banca d'italia", "cr bankitalia"),
    "Estratto conto": ("estratto conto", "estratti conto", "movimenti conto"),
    "DURC": ("durc",),
    "Documento identità": ("documento identita", "documento d'identita", "carta identita"),
    "Dichiarazione fiscale": ("dichiarazione iva", "modello redditi", "unico", "dichiarazione fiscale"),
    "INTRA": ("intra", "intra-2", "intrastat"),
}


@dataclass
class RequestPreview:
    source: str
    external_id: str
    request_text: str
    fingerprint: str
    due_date: str | None
    requested_documents: list[str]
    client_id: str | None
    client_name: str | None
    practice_id: str | None
    practice_code: str | None
    confidence: float
    match_reason: str
    duplicate: bool
    duplicate_reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _fingerprint(text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", _clean(text).casefold())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _parse_due_date(text: str, today: date | None = None) -> str | None:
    today = today or date.today()
    source = _clean(text).casefold()

    numeric = re.search(r"\b(?:entro\s+il\s+|scadenza\s*[:\-]?\s*)?(\d{1,2})[\/.\-](\d{1,2})(?:[\/.\-](\d{2,4}))?\b", source)
    if numeric:
        day, month = int(numeric.group(1)), int(numeric.group(2))
        raw_year = numeric.group(3)
        year = int(raw_year) if raw_year else today.year
        if year < 100:
            year += 2000
        try:
            candidate = date(year, month, day)
            if not raw_year and candidate < today:
                candidate = date(year + 1, month, day)
            return candidate.isoformat()
        except ValueError:
            pass

    names = "|".join(ITALIAN_MONTHS)
    named = re.search(rf"\b(?:entro\s+il\s+|entro\s+|scadenza\s*[:\-]?\s*)?(\d{{1,2}})\s+({names})(?:\s+(\d{{4}}))?\b", source)
    if named:
        day = int(named.group(1))
        month = ITALIAN_MONTHS[named.group(2)]
        year = int(named.group(3)) if named.group(3) else today.year
        try:
            candidate = date(year, month, day)
            if not named.group(3) and candidate < today:
                candidate = date(year + 1, month, day)
            return candidate.isoformat()
        except ValueError:
            pass

    if "domani" in source:
        return (today + timedelta(days=1)).isoformat()
    return None


def _extract_documents(text: str) -> list[str]:
    hay = _clean(text).casefold()
    found: list[str] = []
    for label, patterns in DOCUMENT_PATTERNS.items():
        if any(pattern in hay for pattern in patterns):
            found.append(label)
    return found


def _append_unique(existing: Any, new_value: str, separator: str = "\n") -> str:
    old = _clean(str(existing or ""))
    fresh = _clean(new_value)
    if not fresh:
        return old
    if fresh.casefold() in old.casefold():
        return old
    return fresh if not old else old + separator + fresh


class RequestIntakeService:
    """Controlled request intake: PREPARE -> APPROVE -> APPLY.

    No write to Clienti/Pratiche is performed by prepare().
    approve() writes only after the caller has explicitly confirmed the preview.
    """

    def __init__(self, airtable: AirtableGold):
        self.airtable = airtable

    def _duplicate_status(self, external_id: str, fingerprint: str) -> tuple[bool, str]:
        for value in (external_id, fingerprint):
            if not value:
                continue
            try:
                existing = self.airtable.find_one("eventi", "Record ID", value)
            except Exception:
                existing = None
            if existing:
                fields = existing.get("fields", {})
                action = str(fields.get("Azione") or "")
                status = str(fields.get("Stato") or "")
                if action.startswith("request-intake") and status in {"Ricevuto", "Completato"}:
                    return True, f"Richiesta gia registrata ({value[:16]}...)."
        return False, ""

    def prepare(self, request_text: str, source: str = "ChatGPT Work", external_id: str = "") -> RequestPreview:
        text = _clean(request_text)
        if not text:
            raise ValueError("Testo richiesta mancante")
        fingerprint = _fingerprint(text)
        external_id = _clean(external_id) or f"req_{fingerprint[:24]}"
        match: MatchResult = match_client_practice(self.airtable, text)
        duplicate, duplicate_reason = self._duplicate_status(external_id, fingerprint)
        return RequestPreview(
            source=_clean(source) or "ChatGPT Work",
            external_id=external_id,
            request_text=text,
            fingerprint=fingerprint,
            due_date=_parse_due_date(text),
            requested_documents=_extract_documents(text),
            client_id=match.client_id,
            client_name=match.client_name,
            practice_id=match.practice_id,
            practice_code=match.practice_code,
            confidence=match.confidence,
            match_reason=match.reason,
            duplicate=duplicate,
            duplicate_reason=duplicate_reason,
        )

    def _audit(self, *, record_id: str, action: str, status: str, detail: str, correlation_id: str) -> dict:
        return self.airtable.create_record(
            "eventi",
            {
                "Evento ID": f"evt_{uuid.uuid4().hex}",
                "Data e ora": _now(),
                "Origine": "FinancePlus",
                "Sorgente tecnica": "SMART F+ Request Intake",
                "Tipo evento": "request.intake",
                "Entita": "Pratiche",
                "Record ID": record_id[:500],
                "Azione": action,
                "Stato": status,
                "Dettaglio": detail[:9000],
                "Correlation ID": correlation_id,
            },
        )

    def approve(
        self,
        preview: RequestPreview,
        *,
        client_id: str | None = None,
        practice_id: str | None = None,
        approved_by: str = "Utente SMART F+",
    ) -> dict[str, Any]:
        if preview.duplicate:
            return {"status": "duplicate", "message": preview.duplicate_reason, "practice_id": preview.practice_id}

        correlation_id = uuid.uuid4().hex
        target_practice_id = practice_id or preview.practice_id
        target_client_id = client_id or preview.client_id

        if target_practice_id:
            practice = self.airtable.get_record("pratiche", target_practice_id)
            pf = practice.get("fields", {})
            linked = pf.get("Cliente collegato", [])
            if not target_client_id and isinstance(linked, list) and linked:
                target_client_id = linked[0]
        else:
            practice = None
            pf = {}

        if not target_client_id:
            return {
                "status": "mapping_required",
                "message": "Cliente non identificato: selezionare un cliente prima dell'approvazione.",
            }

        client = self.airtable.get_record("clienti", target_client_id)
        cf = client.get("fields", {})
        client_name = str(cf.get("Cliente") or preview.client_name or "Cliente")

        due = preview.due_date
        docs = ", ".join(preview.requested_documents)
        action_text = preview.request_text
        alert_text = f"Richiesta acquisita da {preview.source}. Approvata da {approved_by}."
        if due:
            alert_text += f" Scadenza {due}."

        if practice:
            updates: dict[str, Any] = {
                "Stato": "Integrazione",
                "Prossima azione": _append_unique(pf.get("Prossima azione"), action_text),
                "Alert e criticita": _append_unique(pf.get("Alert e criticita") or pf.get("Alert e criticità"), alert_text, " | "),
            }
            if due:
                updates["Scadenza prossima azione"] = due
            if docs:
                updates["Documenti mancanti"] = _append_unique(pf.get("Documenti mancanti"), docs, ", ")
                updates["Stato documentazione"] = "Incompleta"
            updated = self.airtable.update_record("pratiche", target_practice_id, updates)
            practice_code = str(updated.get("fields", {}).get("Pratica ID") or preview.practice_code or "")
            operation = "updated"
        else:
            practice_code = f"REQ-{date.today().strftime('%Y%m%d')}-{preview.fingerprint[:6].upper()}"
            fields: dict[str, Any] = {
                "Pratica ID": practice_code,
                "Cliente": client_name,
                "Cliente collegato": [target_client_id],
                "Tipo Pratica": "Altro",
                "Stato": "Integrazione",
                "Priorita": "Alta" if due else "Media",
                "Prossima azione": action_text,
                "Alert e criticita": alert_text,
                "Stato documentazione": "Incompleta" if docs else "Da verificare",
            }
            if due:
                fields["Scadenza prossima azione"] = due
            if docs:
                fields["Documenti mancanti"] = docs
            created = self.airtable.create_record("pratiche", fields)
            target_practice_id = created["id"]
            operation = "created"

        detail = (
            f"{operation.upper()} pratica {practice_code} per {client_name}; "
            f"fonte={preview.source}; external_id={preview.external_id}; "
            f"scadenza={due or '-'}; documenti={docs or '-'}; approvato_da={approved_by}."
        )
        self._audit(
            record_id=preview.external_id or preview.fingerprint,
            action="request-intake-apply",
            status="Completato",
            detail=detail,
            correlation_id=correlation_id,
        )
        if preview.fingerprint != preview.external_id:
            self._audit(
                record_id=preview.fingerprint,
                action="request-intake-fingerprint",
                status="Completato",
                detail=f"Fingerprint richiesta associato a {practice_code}.",
                correlation_id=correlation_id,
            )
        return {
            "status": "applied",
            "operation": operation,
            "practice_id": target_practice_id,
            "practice_code": practice_code,
            "client_id": target_client_id,
            "client_name": client_name,
            "correlation_id": correlation_id,
        }
