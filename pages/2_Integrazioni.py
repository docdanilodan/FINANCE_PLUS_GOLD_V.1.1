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

st.subheader("Plugin ChatGPT — installati e verificati")
plugin_rows = [
    ("Gmail", "Installato", "Connettore ChatGPT disponibile"),
    ("Google Drive", "Installato", "Drive/Docs/Sheets/Slides disponibili"),
    ("Google Calendar", "Installato", "Agenda e disponibilita"),
    ("Google Contacts", "Installato", "Risoluzione contatti e destinatari"),
    ("GitHub", "Installato", "Repository, CI, workflow e modifiche codice"),
    ("Airtable", "Installato", "CRM FinancePlus collegabile e gestibile"),
    ("Render", "Installato", "Deploy, servizi, log e variabili ambiente"),
    ("Supabase", "Installato", "PostgreSQL, migrazioni, Edge Functions"),
    ("Neon", "Installato", "PostgreSQL serverless e gestione database"),
    ("CData Connect AI", "Installato / OK", "Test 07/09/2026 riuscito: cataloghi restituiti"),
    ("Data Analytics", "Installato", "Analisi dati prodotto/business"),
    ("Adobe", "Installato", "Creative Cloud e documenti"),
    ("Adobe Acrobat", "Installato", "PDF, OCR, conversioni e redazione"),
    ("Adobe Express", "Installato", "Materiali grafici e template"),
    ("OpenAI Developers", "Installato", "API OpenAI, Agents SDK e Apps"),
    ("Process Documentation AI", "Installato", "SOP e procedure operative"),
    ("GSC Wizard", "Installato", "Search Console e GA4; connessione account da verificare se usata"),
    ("WordPress.com", "Installato", "Gestione sito WordPress.com"),
    ("Windsor.ai", "Installato", "Connettori marketing e business data"),
    ("Spreadsheets", "Installato di default", "Fogli di calcolo e analisi tabellari"),
]
plugins_df = pd.DataFrame(plugin_rows, columns=["Plugin", "Stato", "Nota"])
st.dataframe(plugins_df, use_container_width=True, hide_index=True)
st.caption("Registro plugin aggiornato al 07/09/2026. Lo stato 'Installato' riguarda ChatGPT; i Secrets del runtime FinancePlus restano separati.")

st.subheader("Plugin consigliati da valutare")
recommended_rows = [
    ("AIR Credit Intelligence", "PRIORITA ALTA", "Non installato", "Scoring/credit intelligence, driver di rischio e scenari forward-looking"),
    ("D&B Finance Analytics", "PRIORITA ALTA se licenziato", "Non installato", "Dati D&B, rischio commerciale, limiti di credito e monitoraggio portafoglio; richiede licenza"),
    ("Photon Commerce", "OPZIONALE", "Non installato", "Secondo motore per estrazione strutturata di fatture/ricevute; utile come controllo incrociato"),
]
recommended_df = pd.DataFrame(recommended_rows, columns=["Plugin", "Priorita", "Stato", "Perche utile a FinancePlus"])
st.dataframe(recommended_df, use_container_width=True, hide_index=True)
st.caption("Scelta consigliata: installare prima AIR Credit Intelligence; D&B solo con licenza; Photon solo se serve ridondanza OCR/documentale.")

st.subheader("Problemi GitHub Actions rilevati — cause certe")
workflow_rows = [
    ("Aruba Archive", "BLOCCATO CONFIGURAZIONE", "ARUBA_D_DANGELO_PASSWORD e ARUBA_PRATICHE_PASSWORD assenti nei GitHub Actions Secrets; nel run risultavano vuoti anche AIRTABLE_TOKEN/AIRTABLE_BASE_ID e Google runtime secrets."),
    ("Drive Classification Sync", "BLOCCATO CONFIGURAZIONE", "FINANCEPLUS_DRIVE_LABEL_MAP_JSON assente/non valido; nel run risultavano vuoti anche Airtable e Google OAuth/profile secrets."),
]
workflow_df = pd.DataFrame(workflow_rows, columns=["Workflow", "Stato", "Causa verificata"])
st.dataframe(workflow_df, use_container_width=True, hide_index=True)
st.warning("Questi due errori non sono bug del codice Python: richiedono il completamento dei GitHub Actions Secrets. Le password/token non devono essere salvati nel repository.")

st.subheader("Priorita operative")
st.markdown(
    """
1. Inserire nei GitHub Actions Secrets le due password Aruba e rieseguire `FinancePlus automatic Aruba archive`.
2. Configurare `FINANCEPLUS_DRIVE_LABEL_MAP_JSON` e i Secrets Google/Airtable richiesti dal Drive sync, poi verificare il marker `DRIVE_RECONCILIATION_OK`.
3. Mantenere Airtable come CRM canonico; usare Supabase/Neon come estensione solo con una migrazione deliberata.
4. Installare AIR Credit Intelligence come primo plugin creditizio aggiuntivo; valutare D&B soltanto se disponibile la licenza.
5. Conservare un solo ramo applicativo: FINANCE_PLUS_UNICO V_1.1 / FINANCE_PLUS_GOLD_GENERALE.
"""
)

st.caption(f"Ultimo rendering pagina: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")