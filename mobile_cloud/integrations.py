from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

PRODUCT = "SMART F+"
ALLOWED_TELEMETRY = {
    "release", "module", "feature", "operation", "status", "result",
    "duration_ms", "error_type", "source", "connector", "mode",
}


def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()


def _safe_props(values: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in (values or {}).items():
        if key not in ALLOWED_TELEMETRY:
            continue
        if isinstance(value, (str, int, float, bool)):
            out[key] = value if not isinstance(value, str) else value[:160]
    return out


def connector_presence() -> dict[str, str]:
    return {
        "sentry": "CONFIGURED" if _env("SENTRY_DSN") else "CREDENTIALS_REQUIRED",
        "posthog": "CONFIGURED" if _env("POSTHOG_HOST") and (_env("POSTHOG_PROJECT_API_KEY") or _env("POSTHOG_API_KEY")) else "CREDENTIALS_REQUIRED",
        "n8n": "CONFIGURED" if _env("N8N_BASE_URL") or _env("N8N_WEBHOOK_URL") else "CREDENTIALS_REQUIRED",
        "infocamere": "CONFIGURED" if _env("INFOCAMERE_BASE_URL") and (_env("INFOCAMERE_API_TOKEN") or _env("INFOCAMERE_API_KEY")) else "CREDENTIALS_REQUIRED",
    }


def _before_send(event, hint):
    if not isinstance(event, dict):
        return None
    event.pop("request", None)
    event.pop("user", None)
    event.pop("extra", None)
    event.pop("breadcrumbs", None)
    event.pop("modules", None)
    event["message"] = "SMART F+ technical event; source content removed"
    box = event.get("exception")
    if isinstance(box, dict) and isinstance(box.get("values"), list):
        cleaned = []
        for item in box["values"][-5:]:
            kind = item.get("type") if isinstance(item, dict) else None
            cleaned.append({"type": str(kind or "ApplicationError")[:80], "value": "[source content removed]"})
        event["exception"] = {"values": cleaned}
    return event


def init_sentry() -> dict[str, Any]:
    dsn = _env("SENTRY_DSN")
    if not dsn:
        return {"ok": False, "status": "CREDENTIALS_REQUIRED"}
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            environment=_env("FPLUS_ENV") or "production",
            release=_env("FPLUS_RELEASE") or "smartfplus-mobile-cloud",
            send_default_pii=False,
            traces_sample_rate=0.0,
            profiles_sample_rate=0.0,
            max_request_body_size="never",
            include_local_variables=False,
            before_send=_before_send,
        )
        return {"ok": True, "status": "READY"}
    except Exception as exc:
        return {"ok": False, "status": "ERROR", "error_type": type(exc).__name__}


def posthog_capture(event: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    host = _env("POSTHOG_HOST").rstrip("/")
    key = _env("POSTHOG_PROJECT_API_KEY") or _env("POSTHOG_API_KEY")
    if not host or not key:
        return {"ok": False, "status": "CREDENTIALS_REQUIRED"}
    body = {
        "api_key": key,
        "event": str(event)[:120],
        "properties": {"distinct_id": "smartfplus-mobile-cloud", **_safe_props(properties)},
    }
    req = urllib.request.Request(
        host + "/capture/",
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "SMARTFPlus-Mobile-Cloud"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return {"ok": 200 <= resp.status < 300, "status_code": resp.status}
    except Exception as exc:
        return {"ok": False, "status": "ERROR", "error_type": type(exc).__name__}


def n8n_emit(event: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    url = _env("N8N_WEBHOOK_URL")
    if not url:
        return {"ok": False, "status": "CREDENTIALS_REQUIRED"}
    body = {"event": str(event)[:120], "source": "smartfplus-mobile-cloud", "payload": _safe_props(properties)}
    req = urllib.request.Request(
        url,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "SMARTFPlus-Mobile-Cloud"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {"ok": 200 <= resp.status < 300, "status_code": resp.status}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": "ERROR", "status_code": exc.code}
    except Exception as exc:
        return {"ok": False, "status": "ERROR", "error_type": type(exc).__name__}


def infocamere_lookup(tax_id: str) -> dict[str, Any]:
    base = _env("INFOCAMERE_BASE_URL").rstrip("/")
    token = _env("INFOCAMERE_API_TOKEN") or _env("INFOCAMERE_API_KEY")
    template = _env("INFOCAMERE_COMPANY_PATH_TEMPLATE")
    if not base or not token or not template:
        return {"ok": False, "status": "CREDENTIALS_REQUIRED"}
    tax_id = re.sub(r"[^A-Za-z0-9]", "", tax_id or "")
    if len(tax_id) < 8 or len(tax_id) > 20:
        return {"ok": False, "status": "INVALID_TAX_ID"}
    path = template.replace("{tax_id}", urllib.parse.quote(tax_id, safe=""))
    if not path.startswith("/"):
        path = "/" + path
    header = _env("INFOCAMERE_AUTH_HEADER") or "Authorization"
    prefix = _env("INFOCAMERE_AUTH_PREFIX") or "Bearer"
    value = (prefix + " " + token).strip() if prefix else token
    req = urllib.request.Request(
        base + path,
        headers={header: value, "Accept": "application/json", "User-Agent": "SMARTFPlus-Mobile-Cloud"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read(500_000)
        data = json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
        return {"ok": True, "status": "READY", "data": data}
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": "ERROR", "status_code": exc.code}
    except Exception as exc:
        return {"ok": False, "status": "ERROR", "error_type": type(exc).__name__}
