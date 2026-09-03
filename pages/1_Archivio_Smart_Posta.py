from __future__ import annotations

import os

import streamlit as st

from modules.archive_smart_ui import render_archive_smart
from services.airtable_adapter import AirtableGold, DEFAULT_BASE_ID

st.set_page_config(page_title="Archivio Smart / Posta", page_icon="📮", layout="wide")


def secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default) or "")


def airtable_client() -> AirtableGold | None:
    token = secret("AIRTABLE_TOKEN")
    if not token:
        return None
    return AirtableGold(token=token, base_id=secret("AIRTABLE_BASE_ID", DEFAULT_BASE_ID))


def google_profiles() -> dict[str, str]:
    profiles: dict[str, str] = {}
    primary = secret("GOOGLE_OAUTH_TOKEN_JSON")
    if primary:
        profiles["PRINCIPALE"] = primary
    try:
        keys = list(st.secrets.keys())
    except Exception:
        keys = []
    prefix = "GOOGLE_OAUTH_TOKEN_JSON_"
    for key in keys:
        key = str(key)
        if not key.startswith(prefix):
            continue
        value = secret(key)
        if value:
            profiles[key[len(prefix):] or key] = value
    return profiles


st.title("📮 FINANCEPLUS — Archivio Smart / Posta")
render_archive_smart(airtable_client(), google_profiles(), secret)
