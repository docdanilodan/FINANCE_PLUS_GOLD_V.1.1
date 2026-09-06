from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Integrazioni FinancePlus", page_icon="🔌", layout="wide")

NAVY = "#0B1F3A"
COPPER = "#C46B32"


def secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default) or "")


def yes_no(value: bool) -> str:
    return "Configurato" if value else "Da configurare"


def runtime_rows() -> list[dict[str, str]]:
    airtable_ok = bool(secret("AIRTABLE_TOKEN") and secret("AIRTABLE_BASE_ID"))
    google_ok = bool(secret("GOOGLE_OAUTH_TOKEN_JSON") and secret("GOOGLE_DRIVE_FOLDER_ID"))
    aruba_dd_ok = bool(secret("ARUBA_D_DANGELO_EMAIL") and secret("ARUBA_D_DANGELO_PASSWORD"))
    aruba_pr_ok = bool(secret("ARUBA_PRATICHE_EMAIL") and secret("ARUBA_PRATICHE_PASSWORD"))
    openai_ok = bool(secret("OPENAI_API_KEY"))
    adobe_ok = bool(secret("PDF_SERVICES_CLIENT_ID") and secret("PDF_SERVICES_CLIENT_SECRET"))
    webhook_ok = bool(secret("FINANCEPLUS_WEBHOOK_SECRET"))
    drive_map = secret("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", "{}")
    try:
        drive_map_ok = bool(json.loads(drive_map or "{}"))
    except Exception:
        drive_map_ok = False

    return [
        {"Integrazione": "Airtable CRM", "Stato runtime": yes_no(airtable_ok), "Uso": "Clienti, pratiche, documenti, analisi"},
        {"Integrazione": "Gmail / Google Drive", "Stato runtime": yes_no(google_ok), "Uso": "Email, allegati, archivio documentale"},
        {"Integrazione": "Aruba d.dangelo@financeplus.tech", "Stato runtime": yes_no(aruba_dd_ok), "Uso": "IMAP multi-account"},
        {"Integrazione": "Aruba pratiche@financeplus.tech", "Stato runtime": yes_no(aruba_pr_ok), "Uso": "IMAP multi-account"},
        {"Integrazione": "OpenAI", "Stato runtime": yes_no(openai_ok), "Uso": "Funzioni AI governate"},
        {"Integrazione": "Adobe PDF Services", "Stato runtime": yes_no(adobe_ok), "Uso": "Estrazione PDF opzionale"},
        {"Integrazione": "Webhook FinancePlus", "Stato runtime": yes_no(webhook_ok), "Uso": "Eventi e automazioni"},
        {"Integrazione": "Drive Label Map", "Stato runtime": yes_no(drive_map_ok), "Uso": "Classificazione documentale"},
    ]


def test_airtable() -> tuple[str, str]:
    token = secret("AIRTABLE_TOKEN")
    base_id = secret("AIRTABLE_BASE_ID")
    if not token or not base_id:
        return "NON CONFIGURATO", "Mancano AIRTABLE_TOKEN e/o AIRTABLE_BASE_ID"
    try:
        r = requests.get(
            f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        if r.ok:
            return "OK", "Connessione API Airtable riuscita"
        return "ERRORE", f"HTTP {r.status_code}"
    except Exception as exc:
        return "ERRORE", str(exc)[:180]


def test_event_api() -> tuple[str, str]:
    base = secret("FINANCEPLUS_EVENT_API_URL", "https://financeplus-events-v2.onrender.com").rstrip("/")
    for path in ("/health", "/"):
        try:
            r = requests.get(base + path, timeout=10)
            if r.status_code < 500:
                return "OK", f"{base + path} -> HTTP {r.status_code}"
        except Exception:
            continue
    return "ERRORE", "Event API non raggiungibile o risposta server 5xx"


st.markdown(
    f"""
    <style>
    .fp-head {{background:linear-gradient(135deg,{NAVY},#102A4C);padding:20px 24px;border-radius:16px;color:white;margin-bottom:18px}}
    .fp-head h1 {{color:white;margin:0 0 4px 0}}
    .fp-head b {{color:{COPPER}}}
    </style>
    <div class="fp-head">
      <h1>🔌 Integrazioni FinancePlus</h1>
      <div>Stato configurazioni applicative, test rapidi e registro plugin ChatGPT.</div>
      <div><b>FINANCE_PLUS_UNICO V_1.1</b></div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.subheader("Stato runtime dell'app")
runtime_df = pd.DataFrame(runtime_rows())
st.dataframe(runtime_df, use_container_width=True, hide_index=True)

configured = int((runtime_df["Stato runtime"] == "Configurato").sum())
cols = st.columns(3)
cols[0].metric("Integrazioni censite", len(runtime_df))
cols[1].metric("Configurate", configured)
cols[2].metric("Da configurare", len(runtime_df) - configured)

st.caption("La pagina mostra solo presenza/configurazione dei Secrets, senza esporre token o password.")

st.subheader("Test sicuri")
if st.button("Esegui test connessioni", type="primary"):
    a_status, a_note = test_airtable()
    e_status, e_note = test_event_api()
    st.dataframe(
        pd.DataFrame([
            {"Servizio": "Airtable", "Esito": a_status, "Dettaglio": a_note},
            {"Servizio": "FinancePlus Event API", "Esito": e_status, "Dettaglio": e_note},
        ]),
        use_container_width=True,
        hide_index=True,
    )
    st.caption("I test non stampano credenziali e non modificano dati.")

st.subheader("Plugin ChatGPT — registro progetto")
plugin_rows = [
    ("Gmail", "Installato", "Operativo lato ChatGPT; runtime FinancePlus dipende dai Secrets Google"),
    ("Google Drive", "Installato", "Operativo lato ChatGPT; runtime FinancePlus dipende dai Secrets Google"),
    ("GitHub", "Installato", "Repository e deploy gestibili"),
    ("Airtable", "Installato", "Base FinancePlus collegata lato ChatGPT"),
    ("Render", "Installato", "Deploy e log gestibili"),
    ("CData Connect AI", "Installato / da verificare", "Ultimo test noto: errore HTTP 500"),
    ("GSC Wizard", "Installato / bloccato", "Ultimo stato noto: piano/trial da riattivare"),
    ("WordPress.com", "Installato", "Disponibile lato ChatGPT"),
    ("Adobe", "Installato", "Disponibile lato ChatGPT"),
    ("Adobe Acrobat", "Installato", "Disponibile lato ChatGPT"),
    ("Google Calendar", "Installato", "Disponibile lato ChatGPT"),
    ("Google Contacts", "Installato", "Disponibile lato ChatGPT"),
    ("MCP Server For WordPress", "Non installato", "Installazione non autorizzata; nessun blocco per le altre integrazioni"),
]
plugins_df = pd.DataFrame(plugin_rows, columns=["Plugin", "Stato", "Nota"])
st.dataframe(plugins_df, use_container_width=True, hide_index=True)
st.caption("Registro informativo aggiornato al 06/09/2026; i plugin ChatGPT non sono interrogabili direttamente dal runtime Streamlit.")

st.subheader("Priorita operative")
st.markdown(
    """
1. Completare i Secrets runtime mancanti senza salvarli nel repository.
2. Portare Gmail/Drive e Aruba a test end-to-end reale.
3. Verificare l'Event API e rimuovere eventuali risposte 5xx.
4. Riattivare GSC Wizard se serve l'analisi Search Console.
5. Riprovare CData Connect AI dopo verifica del servizio/account.
"""
)

st.caption(f"Ultimo rendering pagina: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
