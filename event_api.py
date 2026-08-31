from __future__ import annotations

import hmac
import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from services.event_orchestrator import FinancePlusEventOrchestrator


app = FastAPI(
    title="FinancePlus 360 AI Event API",
    version="1.2.0",
    description="Webhook/event ingress for Airtable, Gmail, GitHub, Work and Drive with staged AI approvals and CSE privacy policy.",
)


class EventPayload(BaseModel):
    source: str = Field(default="Airtable")
    entity: str
    record_id: str
    event_type: str = Field(default="record.changed")
    correlation_id: Optional[str] = None


class ExternalEventPayload(BaseModel):
    external_id: str
    event_type: str = Field(default="external.event")
    detail: Optional[str] = None
    correlation_id: Optional[str] = None


class WorkEventPayload(ExternalEventPayload):
    source_platform: str = Field(default="Gmail")


def _authorize(provided: str | None) -> None:
    expected = os.getenv("FINANCEPLUS_WEBHOOK_SECRET", "")
    if not expected:
        raise HTTPException(status_code=503, detail="FINANCEPLUS_WEBHOOK_SECRET non configurato")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Webhook secret non valido")


def _external(source: str, payload: ExternalEventPayload) -> dict:
    orchestrator = FinancePlusEventOrchestrator()
    return orchestrator.process_external_event(
        source=source,
        event_type=payload.event_type,
        external_id=payload.external_id,
        detail=payload.detail or "",
        correlation_id=payload.correlation_id or "",
    )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "webhook_secret_configured": bool(os.getenv("FINANCEPLUS_WEBHOOK_SECRET")),
        "airtable_configured": bool(os.getenv("AIRTABLE_TOKEN")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "cdata_configured": bool(os.getenv("CDATA_USER") and os.getenv("CDATA_PAT")),
        "ai_staging": os.getenv("FINANCEPLUS_AI_STAGING", "true").lower() not in {"0", "false", "no"},
        "ai_write_back": os.getenv("FINANCEPLUS_AI_WRITE_BACK", "false").lower() in {"1", "true", "yes"},
        "external_webhooks": True,
        "drive_cse_policy": True,
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
    orchestrator = FinancePlusEventOrchestrator()
    return orchestrator.process(
        source="Airtable",
        entity=payload.entity,
        record_id=payload.record_id,
        event_type=payload.event_type,
        correlation_id=payload.correlation_id or "",
    )


@app.post("/events/gmail")
def receive_gmail_event(
    payload: ExternalEventPayload,
    x_financeplus_webhook_secret: str | None = Header(default=None),
) -> dict:
    _authorize(x_financeplus_webhook_secret)
    return _external("Gmail", payload)


@app.post("/events/github")
def receive_github_event(
    payload: ExternalEventPayload,
    x_financeplus_webhook_secret: str | None = Header(default=None),
) -> dict:
    _authorize(x_financeplus_webhook_secret)
    return _external("GitHub", payload)


@app.post("/events/work")
def receive_work_event(
    payload: WorkEventPayload,
    x_financeplus_webhook_secret: str | None = Header(default=None),
) -> dict:
    _authorize(x_financeplus_webhook_secret)
    platform = (payload.source_platform or "unknown")[:100]
    detail = f"Piattaforma sorgente: {platform}. {payload.detail or ''}".strip()
    forwarded = ExternalEventPayload(
        external_id=payload.external_id,
        event_type=payload.event_type,
        detail=detail,
        correlation_id=payload.correlation_id,
    )
    return _external("ChatGPT Work", forwarded)
