from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from services.event_orchestrator import FinancePlusEventOrchestrator


app = FastAPI(
    title="FinancePlus 360 AI Event API",
    version="1.0.0",
    description="Webhook/event ingress for Airtable, Gmail, Drive and FinancePlus automations.",
)


class EventPayload(BaseModel):
    source: str = Field(default="Airtable")
    entity: str
    record_id: str
    event_type: str = Field(default="record.changed")
    correlation_id: Optional[str] = None


def _authorize(provided: str | None) -> None:
    expected = os.getenv("FINANCEPLUS_WEBHOOK_SECRET", "")
    if not expected:
        raise HTTPException(status_code=503, detail="FINANCEPLUS_WEBHOOK_SECRET non configurato")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Webhook secret non valido")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "webhook_secret_configured": bool(os.getenv("FINANCEPLUS_WEBHOOK_SECRET")),
        "airtable_configured": bool(os.getenv("AIRTABLE_TOKEN")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "cdata_configured": bool(os.getenv("CDATA_USER") and os.getenv("CDATA_PAT")),
        "ai_write_back": os.getenv("FINANCEPLUS_AI_WRITE_BACK", "false").lower() in {"1", "true", "yes"},
    }


@app.post("/events")
def receive_event(
    payload: EventPayload,
    x_financeplus_webhook_secret: str | None = Header(default=None),
) -> dict:
    _authorize(x_financeplus_webhook_secret)
    orchestrator = FinancePlusEventOrchestrator()
    return orchestrator.process(
        source=payload.source,
        entity=payload.entity,
        record_id=payload.record_id,
        event_type=payload.event_type,
        correlation_id=payload.correlation_id or "",
    )


@app.post("/events/airtable")
def receive_airtable_event(
    payload: EventPayload,
    x_financeplus_webhook_secret: str | None = Header(default=None),
) -> dict:
    _authorize(x_financeplus_webhook_secret)
    payload.source = "Airtable"
    orchestrator = FinancePlusEventOrchestrator()
    return orchestrator.process(
        source="Airtable",
        entity=payload.entity,
        record_id=payload.record_id,
        event_type=payload.event_type,
        correlation_id=payload.correlation_id or "",
    )
