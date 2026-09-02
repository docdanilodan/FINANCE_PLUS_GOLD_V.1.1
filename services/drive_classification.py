from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


ALLOWED_SENSITIVITY = {"Interno", "Riservato", "Altamente riservato"}


@dataclass
class DriveClassificationDecision:
    sensitivity: str
    source: str = "financeplus-default"
    matched_token: str = ""
    labels_found: int = 0
    error: str = ""


def load_drive_label_mapping() -> dict[str, str]:
    """Load Drive label/field/value -> FinancePlus sensitivity mapping.

    Example:
    FINANCEPLUS_DRIVE_LABEL_MAP_JSON='{
      "SECRET_CHOICE_ID":"Altamente riservato",
      "CONFIDENTIAL_CHOICE_ID":"Riservato",
      "INTERNAL_CHOICE_ID":"Interno"
    }'

    IDs are preferred because Google Drive file labels expose stable IDs even
    when administrators rename the visible label or choice text.
    """
    raw = os.getenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        normalized_key = str(key).strip().casefold()
        sensitivity = str(value).strip()
        if normalized_key and sensitivity in ALLOWED_SENSITIVITY:
            out[normalized_key] = sensitivity
    return out


def _flatten_tokens(value: Any) -> list[str]:
    tokens: list[str] = []
    if value is None:
        return tokens
    if isinstance(value, dict):
        for key, child in value.items():
            tokens.append(str(key))
            tokens.extend(_flatten_tokens(child))
        return tokens
    if isinstance(value, (list, tuple, set)):
        for child in value:
            tokens.extend(_flatten_tokens(child))
        return tokens
    tokens.append(str(value))
    return tokens


def _rank(sensitivity: str) -> int:
    return {
        "Interno": 1,
        "Riservato": 2,
        "Altamente riservato": 3,
    }.get(sensitivity, 0)


def resolve_drive_classification(drive, file_id: str, fallback: str = "Interno") -> DriveClassificationDecision:
    """Read labels already applied to a Drive file and map them to FinancePlus.

    No label is modified here. The function is deliberately read-only and can
    run with the existing Drive scope used by FinancePlus. When no mapping is
    configured, or no mapped value is present, the current FinancePlus
    sensitivity remains authoritative.
    """
    if fallback not in ALLOWED_SENSITIVITY:
        fallback = "Interno"

    mapping = load_drive_label_mapping()
    if not mapping or not file_id:
        return DriveClassificationDecision(sensitivity=fallback)

    try:
        response = drive.files().listLabels(fileId=file_id, maxResults=100).execute()
    except Exception as exc:
        return DriveClassificationDecision(
            sensitivity=fallback,
            source="drive-labels-unavailable",
            error=f"{type(exc).__name__}: {exc}",
        )

    labels = response.get("labels", []) or response.get("items", []) or []
    best = fallback
    matched_token = ""
    for label in labels:
        for token in _flatten_tokens(label):
            mapped = mapping.get(token.strip().casefold())
            if mapped and _rank(mapped) > _rank(best):
                best = mapped
                matched_token = token

    if matched_token:
        return DriveClassificationDecision(
            sensitivity=best,
            source="google-drive-label",
            matched_token=matched_token,
            labels_found=len(labels),
        )
    return DriveClassificationDecision(
        sensitivity=fallback,
        source="google-drive-label-no-match",
        labels_found=len(labels),
    )


def ai_policy_for_sensitivity(sensitivity: str, protection: str = "Standard") -> str:
    if protection == "CSE" or sensitivity == "Altamente riservato":
        return "Bloccata"
    if sensitivity == "Riservato":
        return "Solo con approvazione"
    return "Consentita"
