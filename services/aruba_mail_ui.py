from __future__ import annotations

import os
from datetime import date

import streamlit as st

from services.aruba_imap_pipeline import sync_aruba_attachments, test_aruba_connection


def _secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default) or "")


def _accounts() -> list[dict[str, str]]:
    return [
        {
            "label": "D.Dangelo@financeplus.tech",
            "email": _secret("ARUBA_D_DANGELO_EMAIL", "d.dangelo@financeplus.tech"),
            "password": _secret("ARUBA_D_DANGELO_PASSWORD"),
        },
        {
            "label": "Pratiche@financeplus.tech",
            "email": _secret("ARUBA_PRATICHE_EMAIL", "pratiche@financeplus.tech"),
            "password": _secret("ARUBA_PRATICHE_PASSWORD"),
        },
    ]


def _prepare_shared_secrets() -> None:
    airtable = _secret("AIRTABLE_TOKEN")
    if airtable:
        os.environ["AIRTABLE_TOKEN"] = airtable
    base_id = _secret("AIRTABLE_BASE_ID")
    if base_id:
        os.environ["AIRTABLE_BASE_ID"] = base_id
    google = _secret("GOOGLE_OAUTH_TOKEN_JSON")
    if google:
        os.environ["GOOGLE_OAUTH_TOKEN_JSON"] = google


def render_aruba_mail_sidebar() -> None:
    accounts = _accounts()
    with st.sidebar.expander("📨 Aruba Mail", expanded=False):
        st.caption("IMAP Aruba multi-account • password solo nei Secrets")
        configured = [a for a in accounts if a["password"]]
        st.write(f"Account configurati: **{len(configured)}/2**")
        for account in accounts:
            icon = "✅" if account["password"] else "⚠️"
            st.write(f"{icon} {account['label']}")

        selected_label = st.selectbox(
            "Casella Aruba",
            [a["label"] for a in accounts],
            key="aruba_account_selector",
        )
        selected = next(a for a in accounts if a["label"] == selected_label)

        since = st.date_input(
            "Email dal",
            value=date(2026, 1, 1),
            key="aruba_since",
        )
        max_messages = st.number_input(
            "Messaggi massimi",
            min_value=1,
            max_value=5000,
            value=200,
            step=50,
            key="aruba_max_messages",
        )
        drive_folder = st.text_input(
            "Drive folder ID (opzionale)",
            value=_secret("GOOGLE_DRIVE_FOLDER_ID"),
            key="aruba_drive_folder",
        )

        c1, c2 = st.columns(2)
        if c1.button("🔌 Test", use_container_width=True, key="aruba_test"):
            if not selected["password"]:
                st.error("Password non presente nei Secrets Streamlit.")
            else:
                try:
                    result = test_aruba_connection(selected["email"], selected["password"])
                    st.success(
                        f"Connessione OK: {result['account']} • INBOX {result['inbox_messages']} messaggi"
                    )
                except Exception as exc:
                    st.error(f"Connessione Aruba non riuscita: {exc}")

        if c2.button("🔄 Sincronizza", use_container_width=True, key="aruba_sync"):
            if not selected["password"]:
                st.error("Password non presente nei Secrets Streamlit.")
            elif not _secret("AIRTABLE_TOKEN"):
                st.error("AIRTABLE_TOKEN non configurato.")
            elif not _secret("GOOGLE_OAUTH_TOKEN_JSON"):
                st.error("GOOGLE_OAUTH_TOKEN_JSON non configurato: serve per archiviare gli allegati su Drive.")
            else:
                try:
                    _prepare_shared_secrets()
                    with st.spinner(f"Sincronizzazione {selected['email']}..."):
                        result = sync_aruba_attachments(
                            account_email=selected["email"],
                            password=selected["password"],
                            since=since,
                            drive_folder_id=drive_folder or None,
                            max_messages=int(max_messages),
                        )
                    st.success(
                        f"Completata: {result['messages']} email, {result['attachments']} allegati, "
                        f"{result['uploaded']} caricati, {result['duplicates']} duplicati."
                    )
                    if result.get("errors"):
                        st.warning(f"Errori: {len(result['errors'])}")
                        st.json(result["errors"][:20])
                except Exception as exc:
                    st.error(f"Sincronizzazione Aruba non riuscita: {exc}")

        st.caption("Server: imaps.aruba.it:993 SSL/TLS. Nessuna password viene scritta su GitHub.")
