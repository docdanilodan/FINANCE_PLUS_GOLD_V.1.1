from __future__ import annotations

import re
from dataclasses import dataclass

from services.airtable_adapter import AirtableGold


@dataclass
class MatchResult:
    client_id: str | None = None
    client_name: str | None = None
    practice_id: str | None = None
    practice_code: str | None = None
    confidence: float = 0.0
    reason: str = "Nessuna corrispondenza certa"


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def match_client_practice(
    airtable: AirtableGold,
    text: str,
    clients: list[dict] | None = None,
    practices: list[dict] | None = None,
) -> MatchResult:
    hay = _norm(text)
    if not hay:
        return MatchResult()
    clients = (
        clients
        if clients is not None
        else airtable.list_records("clienti", max_records=2000)
    )
    scored = []
    for rec in clients:
        f = rec.get("fields", {})
        candidates = {
            "Partita IVA": f.get("Partita IVA", ""),
            "Codice Fiscale": f.get("Codice Fiscale", ""),
            "PEC": f.get("PEC", ""),
            "REA": f.get("REA", ""),
            "Cliente": f.get("Cliente", ""),
        }
        score, reason = 0.0, ""
        for field, value in candidates.items():
            token = _norm(str(value))
            if token and len(token) >= 5 and token in hay:
                candidate_score = (
                    0.99
                    if field in ("Partita IVA", "Codice Fiscale")
                    else 0.92
                    if field in ("PEC", "REA")
                    else 0.80
                )
                if candidate_score > score:
                    score, reason = candidate_score, f"Match su {field}"
        if score:
            scored.append((score, rec, reason))
    if not scored:
        return MatchResult()
    scored.sort(key=lambda x: x[0], reverse=True)
    score, client, reason = scored[0]
    cf = client.get("fields", {})
    result = MatchResult(
        client_id=client["id"],
        client_name=cf.get("Cliente"),
        confidence=score,
        reason=reason,
    )
    practices = (
        practices
        if practices is not None
        else airtable.list_records("pratiche", max_records=2000)
    )
    practice_candidates = []
    for rec in practices:
        f = rec.get("fields", {})
        linked = f.get("Cliente collegato", [])
        if result.client_id in linked or _norm(str(f.get("Cliente", ""))) == _norm(
            str(result.client_name or "")
        ):
            code = str(f.get("Pratica ID", ""))
            institution = str(f.get("Istituto", ""))
            pscore = 0.60
            if code and _norm(code) in hay:
                pscore = 0.98
            elif institution and _norm(institution) in hay:
                pscore = 0.88
            practice_candidates.append((pscore, rec))
    if practice_candidates:
        practice_candidates.sort(key=lambda x: x[0], reverse=True)
        pscore, practice = practice_candidates[0]
        pf = practice.get("fields", {})
        result.practice_id = practice["id"]
        result.practice_code = pf.get("Pratica ID")
        result.confidence = (
            min(result.confidence, pscore) if pscore >= 0.80 else result.confidence
        )
        result.reason += "; pratica associata"
    return result


def missing_documents_for_practice(
    airtable: AirtableGold, practice_record: dict
) -> list[str]:
    required = ["Visura", "Bilancio", "Centrale Rischi", "Documento identità"]
    p = practice_record.get("fields", {})
    doc_ids = p.get("Documenti", [])
    docs = airtable.get_records_by_ids("documenti", doc_ids, max_records=200)
    present = {
        str(d.get("fields", {}).get("Tipo Documento", "")).casefold() for d in docs
    }
    return [name for name in required if name.casefold() not in present]


def build_practice_alert(practice_record: dict, missing: list[str]) -> str:
    f = practice_record.get("fields", {})
    alerts = []
    if missing:
        alerts.append("Documenti mancanti: " + ", ".join(missing))
    if not f.get("Prossima azione"):
        alerts.append("Prossima azione non impostata")
    if not f.get("Responsabile pratica"):
        alerts.append("Responsabile pratica non assegnato")
    return " | ".join(alerts)
