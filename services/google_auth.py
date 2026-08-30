from __future__ import annotations

import json
import os
import re
from typing import Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
]

DEFAULT_PROFILE = "DEFAULT"
TOKEN_PREFIX = "GOOGLE_OAUTH_TOKEN_JSON"


def _normalize_profile(profile: str | None) -> str:
    raw = (profile or DEFAULT_PROFILE).strip().upper()
    clean = re.sub(r"[^A-Z0-9_]+", "_", raw).strip("_")
    return clean or DEFAULT_PROFILE


def token_env_name(profile: str | None = None) -> str:
    normalized = _normalize_profile(profile)
    if normalized == DEFAULT_PROFILE:
        return TOKEN_PREFIX
    return f"{TOKEN_PREFIX}_{normalized}"


def discover_google_profiles(configured: Iterable[str] | None = None) -> list[str]:
    """Return enabled Google profiles in deterministic order.

    Profiles can be declared with FINANCEPLUS_GOOGLE_PROFILES, for example:
    DEFAULT,STUDIO,PRATICHE. When it is omitted, the historical default token is
    used and well-known optional profiles are auto-detected when present.
    """
    if configured is None:
        raw = os.getenv("FINANCEPLUS_GOOGLE_PROFILES", "").strip()
        configured = [item for item in raw.split(",") if item.strip()] if raw else []

    profiles: list[str] = []
    for item in configured:
        profile = _normalize_profile(item)
        if profile not in profiles:
            profiles.append(profile)

    if not profiles:
        if os.getenv(TOKEN_PREFIX, "").strip():
            profiles.append(DEFAULT_PROFILE)
        for optional in ("STUDIO", "PRATICHE"):
            if os.getenv(token_env_name(optional), "").strip():
                profiles.append(optional)

    return profiles


def load_credentials(profile: str | None = None) -> Credentials:
    env_name = token_env_name(profile)
    raw = os.getenv(env_name, "").strip()
    if not raw:
        raise RuntimeError(f"{env_name} non configurato")

    info = json.loads(raw)
    creds = Credentials.from_authorized_user_info(info, scopes=SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds.valid:
        raise RuntimeError(f"Credenziali Google non valide o scope insufficienti per {env_name}")
    return creds
