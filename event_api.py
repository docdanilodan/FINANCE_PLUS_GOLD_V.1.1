from __future__ import annotations

import hmac
import os
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from services.event_orchestrator import FinancePlusEventOrchestrator


app = FastAPI(
    title="FinancePlus 360 AI Event API",
    version="1.3.0",
    description="Webhook/event ingress for Airtable, Gmail, GitHub, Work and Drive with staged AI approvals, CSE privacy and GitHub OIDC.",
)

GITHUB_OIDC_ISSUER = "https://token.actions.githubusercontent.com"
GITHUB_OIDC_JWKS = f"{GITHUB_OIDC_ISSUER}/.well-known/jwks"
GITHUB_OIDC_AUDIENCE = "financeplus-events-v2"
GITHUB_ALLOWED_REPOSITORY = os.getenv(
    "FINANCEPLUS_GITHUB_REPOSITORY",
    "docdanilodan/FINANCE_PLUS_GOLD_V.1.1",
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


def _secret_is_valid(provided: str | None) -> bool:
    expected = os.getenv("FINANCEPLUS_WEBHOOK_SECRET", "")
    return bool(expected and provided and hmac.compare_digest(provided, expected))


def _authorize(provided: str | None) -> None:
    expected = os.getenv("FINANCEPLUS_WEBHOOK_SECRET", "")
    if not expected:
        raise HTTPException(status_code=503, detail="FINANCEPLUS_WEBHOOK_SECRET non configurato")
    if not _secret_is_valid(provided):
        raise HTTPException(status_code=401, detail="Webhook secret non valido")


def _authorize_github_oidc(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="GitHub OIDC token mancante")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        signing_key = PyJWKClient(GITHUB_OIDC_JWKS).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=GITHUB_OIDC_AUDIENCE,
            issuer=GITHUB_OIDC_ISSUER,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="GitHub OIDC token non valido") from exc

    if claims.get("repository") != GITHUB_ALLOWED_REPOSITORY:
        raise HTTPException(status_code=403, detail="Repository GitHub non autorizzato")
    workflow_ref = str(claims.get("workflow_ref", ""))
    expected_prefix = f"{GITHUB_ALLOWED_REPOSITORY}/.github/workflows/"
    if not workflow_ref.startswith(expected_prefix):
        raise HTTPException(status_code=403, detail="Workflow GitHub non autorizzato")


def _authorize_external(
    provided_secret: str | None,
    authorization: str | None,
) -> None:
    if _secret_is_valid(provided_secret):
        return
    _authorize_github_oidc(authorization)


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
        "github_oidc": True,
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
    authorization: str | None = Header(default=None),
) -> dict:
    _authorize_external(x_financeplus_webhook_secret, authorization)
    return _external("Gmail", payload)


@app.post("/events/github")
def receive_github_event(
    payload: ExternalEventPayload,
    x_financeplus_webhook_secret: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    _authorize_external(x_financeplus_webhook_secret, authorization)
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
