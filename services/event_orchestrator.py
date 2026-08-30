from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from services.airtable_adapter import AirtableGold


ENTITY_TABLE = {
    "Clienti": "clienti",
    "Pratiche": "pratiche",
    "Documenti": "documenti",
    "Email": "email",
    "Analisi Creditizie": "analisi",
}

HIGHLY_CONFIDENTIAL_TYPES = {
    "Centrale Rischi",
    "Estratto conto",
    "Dichiarazione fiscale",
    "Documento identità",
}
CONFIDENTIAL_TYPES = {
    "Bilancio",
    "Situazione contabile",
    "Contratto",
    "Fattura",
    "Atto societario",
}


class FinancePlusEventOrchestrator:
    def __init__(self, airtable: AirtableGold | None = None):
        self.airtable = airtable or AirtableGold()
        self.ai_write_back = os.getenv("FINANCEPLUS_AI_WRITE_BACK", "false").lower() in {"1", "true", "yes"}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _audit(
        self,
        *,
        event_id: str,
        source: str,
        event_type: str,
        entity: str,
        record_id: str,
        action: str,
        status: str,
        detail: str = "",
        correlation_id: str = "",
    ) -> dict:
        return self.airtable.create_record(
            "eventi",
            {
                "Evento ID": event_id,
                "Data e ora": self._now(),
                "Origine": source if source in {"Airtable", "Gmail", "Google Drive", "CData", "OpenAI", "FinancePlus"} else "FinancePlus",
                "Tipo evento": event_type,
                "Entità": entity,
                "Record ID": record_id,
                "Azione": action,
                "Stato": status,
                "Dettaglio": (detail or "")[:9000],
                "Correlation ID": correlation_id,
            },
        )

    @staticmethod
    def _document_sensitivity(document_type: str) -> str:
        if document_type in HIGHLY_CONFIDENTIAL_TYPES:
            return "Altamente riservato"
        if document_type in CONFIDENTIAL_TYPES:
            return "Riservato"
        if document_type in {"Visura camerale", "DURC", "Preventivo"}:
            return "Interno"
        return "Interno"

    def _handle_document(self, record_id: str, fields: Dict[str, Any]) -> tuple[str, str, str]:
        document_type = str(fields.get("Tipo Documento") or "")
        sensitivity = str(fields.get("Sensibilità dati") or "")

        if not sensitivity:
            sensitivity = self._document_sensitivity(document_type)
            self.airtable.update_record("documenti", record_id, {"Sensibilità dati": sensitivity})

        if sensitivity == "Altamente riservato":
            return (
                "privacy-gate",
                "Ignorato",
                "Documento classificato Altamente riservato: nessun invio automatico a servizi AI esterni.",
            )

        return (
            "classificazione-documento",
            "Completato",
            f"Documento classificato come {sensitivity}. Elaborazione AI consentita solo dai moduli esplicitamente abilitati.",
        )

    def _handle_practice(self, record_id: str, fields: Dict[str, Any]) -> tuple[str, str, str]:
        documentation_status = str(fields.get("Stato documentazione") or "")
        if documentation_status != "Completa":
            return (
                "readiness-check",
                "Ignorato",
                f"Stato documentazione: {documentation_status or 'non valorizzato'}. Nessuna analisi automatica avviata.",
            )

        try:
            from services.openai_responses import OpenAIResponsesClient

            recommendation = OpenAIResponsesClient().operational_recommendation("Pratica", fields)
        except Exception as exc:
            return (
                "ai-readiness",
                "Errore",
                f"Documentazione completa, ma analisi AI non eseguita: {type(exc).__name__}: {exc}",
            )

        if self.ai_write_back and recommendation:
            self.airtable.update_record("pratiche", record_id, {"Prossima azione": recommendation[:9000]})
            return ("ai-readiness", "Completato", "Raccomandazione AI generata e salvata in Prossima azione.")

        return (
            "ai-readiness",
            "Completato",
            "Raccomandazione AI generata; write-back disattivato. Anteprima: " + recommendation[:1200],
        )

    def process(
        self,
        *,
        source: str,
        entity: str,
        record_id: str,
        event_type: str = "record.changed",
        correlation_id: str = "",
    ) -> Dict[str, Any]:
        event_id = f"evt_{uuid.uuid4().hex}"
        correlation_id = correlation_id or uuid.uuid4().hex
        table = ENTITY_TABLE.get(entity)
        if not table:
            self._audit(
                event_id=event_id,
                source=source,
                event_type=event_type,
                entity=entity,
                record_id=record_id,
                action="route",
                status="Ignorato",
                detail="Entità non supportata dall'orchestratore.",
                correlation_id=correlation_id,
            )
            return {"event_id": event_id, "status": "ignored", "reason": "unsupported entity"}

        self._audit(
            event_id=event_id,
            source=source,
            event_type=event_type,
            entity=entity,
            record_id=record_id,
            action="receive",
            status="Ricevuto",
            correlation_id=correlation_id,
        )

        try:
            record = self.airtable.get_record(table, record_id)
            fields = record.get("fields", {})

            if entity == "Documenti":
                action, status, detail = self._handle_document(record_id, fields)
            elif entity == "Pratiche":
                action, status, detail = self._handle_practice(record_id, fields)
            else:
                action, status, detail = (
                    "audit-only",
                    "Completato",
                    "Evento registrato. Nessuna azione automatica distruttiva prevista per questa entità.",
                )

            self._audit(
                event_id=f"{event_id}_result",
                source="FinancePlus",
                event_type=event_type,
                entity=entity,
                record_id=record_id,
                action=action,
                status=status,
                detail=detail,
                correlation_id=correlation_id,
            )
            return {
                "event_id": event_id,
                "correlation_id": correlation_id,
                "status": status,
                "action": action,
                "detail": detail,
            }
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            self._audit(
                event_id=f"{event_id}_error",
                source="FinancePlus",
                event_type=event_type,
                entity=entity,
                record_id=record_id,
                action="process",
                status="Errore",
                detail=detail,
                correlation_id=correlation_id,
            )
            raise
