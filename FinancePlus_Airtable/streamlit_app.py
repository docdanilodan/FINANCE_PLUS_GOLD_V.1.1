from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from airtable_client import AirtableAPIError, AirtableClient


APP_NAME = "FinancePlus Airtable"
DEFAULT_BASE_ID = "appoNJtS64JIcZUhT"

TABLES = {
    "Clienti": "Clienti",
    "Pratiche": "Pratiche",
    "Documenti": "Documenti",
    "Email": "Email",
    "Analisi Creditizie": "Analisi Creditizie",
}

CLIENT_FIELDS = [
    "Cliente", "Partita IVA", "Codice Fiscale", "PEC", "Email", "Stato Cliente",
    "REA", "Sede legale", "Comune", "Provincia", "CAP", "Forma giuridica",
    "Stato attività", "ATECO", "Attività prevalente", "Capitale sociale EUR",
    "Rappresentante/Amministratore", "Data estrazione visura", "N. visure presenti",
    "File sorgente visura", "Stato verifica anagrafica", "CR aggiornata al",
    "Ultimo bilancio disponibile", "Rating FinancePlus", "Note",
]

PRACTICE_FIELDS = [
    "Pratica ID", "Cliente", "Tipo Pratica", "Istituto", "Importo Richiesto", "Stato",
    "Priorità", "Responsabile pratica", "Data Apertura", "Scadenza", "Prossima azione",
    "Scadenza prossima azione", "Stato documentazione", "Completezza dossier",
    "Probabilità delibera", "Importo massimo stimato", "Alert e criticità",
    "Documenti mancanti", "Note",
]

DOCUMENT_FIELDS = [
    "Documento", "Cliente", "Pratica ID", "Tipo Documento", "Esercizio", "Data Documento",
    "Nome Originale", "Nome IA Suggerito", "Nome Definitivo", "Origine", "URL Drive",
    "Sintesi IA", "Stato Verifica",
]

EMAIL_FIELDS = [
    "Oggetto", "Data e ora", "Mittente", "Cliente", "Pratica ID", "Sintesi IA", "Allegati",
    "Priorità", "Azione Richiesta", "Gestita",
]

ANALYSIS_FIELDS = [
    "Analisi ID", "Cliente", "Data Analisi", "Esercizio", "Ricavi", "EBITDA", "EBITDA Margin",
    "PFN", "PFN EBITDA", "DSCR", "Patrimonio Netto", "Score", "Rating",
    "Importo Sostenibile Min", "Importo Sostenibile Max", "Punti di Forza", "Criticità",
    "Raccomandazione IA",
]

st.set_page_config(page_title=APP_NAME, page_icon="📊", layout="wide")


def secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def normalize_value(value: Any) -> Any:
    if isinstance(value, dict) and "name" in value:
        return value.get("name")
    if isinstance(value, list):
        if value and isinstance(value[0], dict) and "name" in value[0]:
            return ", ".join(str(v.get("name", "")) for v in value)
        return ", ".join(str(v) for v in value)
    return value


def records_to_df(records: List[Dict[str, Any]], fields: List[str]) -> pd.DataFrame:
    rows = []
    for record in records:
        source = record.get("fields", {})
        row = {field: normalize_value(source.get(field)) for field in fields}
        row["_record_id"] = record.get("id")
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=fields + ["_record_id"])
    return pd.DataFrame(rows)


@st.cache_data(ttl=60, show_spinner=False)
def load_table(token: str, base_id: str, table: str, fields: tuple[str, ...]):
    client = AirtableClient(token=token, base_id=base_id)
    return client.list_records(table, fields=fields)


def refresh() -> None:
    st.cache_data.clear()
    st.rerun()


def age_days(value: Any) -> int | None:
    if value in (None, "", pd.NaT):
        return None
    try:
        dt = pd.to_datetime(value).date()
        return (date.today() - dt).days
    except Exception:
        return None


def format_currency(value: Any) -> str:
    try:
        return f"€ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def connection_panel() -> tuple[str, str]:
    token = secret("AIRTABLE_TOKEN")
    base_id = secret("AIRTABLE_BASE_ID", DEFAULT_BASE_ID)

    with st.sidebar:
        st.header("FinancePlus Airtable")
        st.caption("CRM e anagrafica camerale")
        st.write(f"Base: `{base_id}`")
        if st.button("🔄 Aggiorna dati", use_container_width=True):
            refresh()

    if not token:
        st.error("Manca AIRTABLE_TOKEN nei Secrets di Streamlit.")
        st.markdown(
            """
### Configurazione richiesta
In **Streamlit Cloud → App settings → Secrets** inserisci:

```toml
AIRTABLE_TOKEN = "pat_xxxxxxxxx"
AIRTABLE_BASE_ID = "appoNJtS64JIcZUhT"
```

Il token deve avere almeno accesso in lettura alla base **FinancePlus AI**. Non inserire mai il token nel codice GitHub.
"""
        )
        st.stop()
    return token, base_id


def load_df(token: str, base_id: str, table: str, fields: List[str]) -> pd.DataFrame:
    try:
        records = load_table(token, base_id, table, tuple(fields))
        return records_to_df(records, fields)
    except AirtableAPIError as exc:
        st.error(str(exc))
        st.stop()


def dashboard(token: str, base_id: str) -> None:
    clienti = load_df(token, base_id, TABLES["Clienti"], CLIENT_FIELDS)
    pratiche = load_df(token, base_id, TABLES["Pratiche"], PRACTICE_FIELDS)
    documenti = load_df(token, base_id, TABLES["Documenti"], DOCUMENT_FIELDS)
    email = load_df(token, base_id, TABLES["Email"], EMAIL_FIELDS)
    analisi = load_df(token, base_id, TABLES["Analisi Creditizie"], ANALYSIS_FIELDS)

    st.title("📊 FinancePlus Airtable")
    st.caption("Cruscotto operativo collegato alla base Airtable FinancePlus AI")

    stale = clienti["Data estrazione visura"].apply(age_days).fillna(-1) > 180
    stale_count = int(stale.sum())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Clienti", len(clienti))
    c2.metric("Pratiche", len(pratiche))
    c3.metric("Documenti", len(documenti))
    c4.metric("Email", len(email))
    c5.metric("Visure > 180 gg", stale_count)

    st.subheader("Situazione operativa")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### Visure da aggiornare")
        view = clienti.loc[stale, ["Cliente", "Partita IVA", "Data estrazione visura", "Stato verifica anagrafica"]].copy()
        if view.empty:
            st.success("Nessuna visura oltre 180 giorni.")
        else:
            st.dataframe(view, use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("#### Pratiche aperte / in lavorazione")
        if pratiche.empty:
            st.info("Nessuna pratica disponibile.")
        else:
            view = pratiche[["Pratica ID", "Cliente", "Stato", "Priorità", "Istituto", "Importo Richiesto"]].copy()
            st.dataframe(view, use_container_width=True, hide_index=True)

    st.markdown("#### Ultime email indicizzate")
    if email.empty:
        st.info("Nessuna email indicizzata.")
    else:
        temp = email.copy()
        temp["_data"] = pd.to_datetime(temp["Data e ora"], errors="coerce")
        temp = temp.sort_values("_data", ascending=False).head(10)
        st.dataframe(
            temp[["Data e ora", "Mittente", "Cliente", "Oggetto", "Priorità", "Gestita"]],
            use_container_width=True,
            hide_index=True,
        )

    if not analisi.empty:
        st.markdown("#### Analisi creditizie")
        st.dataframe(
            analisi[["Cliente", "Data Analisi", "Score", "Rating", "DSCR", "PFN EBITDA"]],
            use_container_width=True,
            hide_index=True,
        )


def client_page(token: str, base_id: str) -> None:
    df = load_df(token, base_id, TABLES["Clienti"], CLIENT_FIELDS)
    st.title("👥 Clienti")
    st.caption(f"{len(df)} anagrafiche presenti nella base")

    q = st.text_input("Cerca cliente", placeholder="Ragione sociale, P.IVA, PEC, REA, comune...")
    f1, f2, f3 = st.columns(3)
    province = sorted([x for x in df["Provincia"].dropna().astype(str).unique() if x])
    states = sorted([x for x in df["Stato attività"].dropna().astype(str).unique() if x])
    checks = sorted([x for x in df["Stato verifica anagrafica"].dropna().astype(str).unique() if x])
    provincia = f1.selectbox("Provincia", ["Tutte"] + province)
    stato = f2.selectbox("Stato attività", ["Tutti"] + states)
    verifica = f3.selectbox("Verifica", ["Tutte"] + checks)

    filtered = df.copy()
    if q:
        searchable = filtered.fillna("").astype(str).agg(" ".join, axis=1).str.lower()
        filtered = filtered[searchable.str.contains(q.lower(), regex=False)]
    if provincia != "Tutte":
        filtered = filtered[filtered["Provincia"] == provincia]
    if stato != "Tutti":
        filtered = filtered[filtered["Stato attività"] == stato]
    if verifica != "Tutte":
        filtered = filtered[filtered["Stato verifica anagrafica"] == verifica]

    cols = [
        "Cliente", "Partita IVA", "PEC", "REA", "Comune", "Provincia", "ATECO",
        "Rappresentante/Amministratore", "Data estrazione visura", "Stato verifica anagrafica",
    ]
    st.dataframe(filtered[cols], use_container_width=True, hide_index=True)

    if filtered.empty:
        return

    st.divider()
    selected = st.selectbox("Apri scheda cliente", filtered["Cliente"].dropna().tolist())
    row = filtered.loc[filtered["Cliente"] == selected].iloc[0]

    st.subheader(str(selected))
    a, b, c = st.columns(3)
    a.metric("P.IVA", row.get("Partita IVA") or "—")
    b.metric("REA", row.get("REA") or "—")
    c.metric("Rating", row.get("Rating FinancePlus") or "—")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Anagrafica")
        st.write(f"**Codice fiscale:** {row.get('Codice Fiscale') or '—'}")
        st.write(f"**PEC:** {row.get('PEC') or '—'}")
        st.write(f"**Email:** {row.get('Email') or '—'}")
        st.write(f"**Forma giuridica:** {row.get('Forma giuridica') or '—'}")
        st.write(f"**Stato attività:** {row.get('Stato attività') or '—'}")
        st.write(f"**Sede legale:** {row.get('Sede legale') or '—'}")
        st.write(f"**CAP / Comune / Provincia:** {row.get('CAP') or '—'} / {row.get('Comune') or '—'} / {row.get('Provincia') or '—'}")

    with right:
        st.markdown("#### Profilo camerale")
        st.write(f"**ATECO:** {row.get('ATECO') or '—'}")
        st.write(f"**Attività prevalente:** {row.get('Attività prevalente') or '—'}")
        st.write(f"**Capitale sociale:** {format_currency(row.get('Capitale sociale EUR'))}")
        st.write(f"**Amministratore:** {row.get('Rappresentante/Amministratore') or '—'}")
        st.write(f"**Ultima visura:** {row.get('Data estrazione visura') or '—'}")
        st.write(f"**N. visure:** {row.get('N. visure presenti') or '—'}")
        st.write(f"**Stato verifica:** {row.get('Stato verifica anagrafica') or '—'}")

    st.markdown("#### Dossier FinancePlus")
    d1, d2, d3 = st.columns(3)
    d1.write(f"**CR aggiornata al:** {row.get('CR aggiornata al') or '—'}")
    d2.write(f"**Ultimo bilancio:** {row.get('Ultimo bilancio disponibile') or '—'}")
    d3.write(f"**File visura:** {row.get('File sorgente visura') or '—'}")
    if row.get("Note"):
        st.info(str(row.get("Note")))


def generic_page(token: str, base_id: str, title: str, fields: List[str]) -> None:
    df = load_df(token, base_id, TABLES[title], fields)
    st.title(title)
    st.caption(f"{len(df)} record")
    q = st.text_input("Ricerca", key=f"search_{title}")
    filtered = df.copy()
    if q:
        searchable = filtered.fillna("").astype(str).agg(" ".join, axis=1).str.lower()
        filtered = filtered[searchable.str.contains(q.lower(), regex=False)]
    visible = [c for c in fields if c in filtered.columns]
    st.dataframe(filtered[visible], use_container_width=True, hide_index=True)


def main() -> None:
    token, base_id = connection_panel()
    with st.sidebar:
        page = st.radio(
            "Navigazione",
            ["Dashboard", "Clienti", "Pratiche", "Documenti", "Email", "Analisi Creditizie"],
        )
        st.divider()
        st.caption("FinancePlus Airtable v1.0")

    if page == "Dashboard":
        dashboard(token, base_id)
    elif page == "Clienti":
        client_page(token, base_id)
    elif page == "Pratiche":
        generic_page(token, base_id, "Pratiche", PRACTICE_FIELDS)
    elif page == "Documenti":
        generic_page(token, base_id, "Documenti", DOCUMENT_FIELDS)
    elif page == "Email":
        generic_page(token, base_id, "Email", EMAIL_FIELDS)
    elif page == "Analisi Creditizie":
        generic_page(token, base_id, "Analisi Creditizie", ANALYSIS_FIELDS)


if __name__ == "__main__":
    main()
