from __future__ import annotations

from datetime import date
import re
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from airtable_client import AirtableAPIError, AirtableClient


APP_NAME = "FinancePlus Airtable"
APP_VERSION = "1.2"
DEFAULT_BASE_ID = "appoNJtS64JIcZUhT"

TABLES = {
    "Clienti": "Clienti",
    "Pratiche": "Pratiche",
    "Documenti": "Documenti",
    "Email": "Email",
    "Analisi Creditizie": "Analisi Creditizie",
}

CLIENT_STATUSES = ["Attivo", "Potenziale", "Inattivo"]
PRACTICE_TYPES = [
    "Finanziamento", "Factoring", "Leasing", "Fideiussione",
    "Analisi creditizia", "Business plan", "Altro",
]
PRACTICE_STATUSES = [
    "Da avviare", "Documenti richiesti", "In istruttoria", "Integrazione",
    "Deliberata", "Erogata", "Respinta", "Sospesa",
]
PRACTICE_PRIORITIES = ["Alta", "Media", "Bassa"]
DOCUMENTATION_STATUSES = ["Da verificare", "Incompleta", "Completa"]

CLIENT_FIELDS = [
    "Cliente", "Partita IVA", "Codice Fiscale", "PEC", "Email", "Stato Cliente",
    "REA", "Sede legale", "Comune", "Provincia", "CAP", "Forma giuridica",
    "Stato attività", "ATECO", "Attività prevalente", "Capitale sociale EUR",
    "Rappresentante/Amministratore", "Data estrazione visura", "N. visure presenti",
    "File sorgente visura", "Stato verifica anagrafica", "CR aggiornata al",
    "Ultimo bilancio disponibile", "Rating FinancePlus", "Note",
]

PRACTICE_FIELDS = [
    "Pratica ID", "Cliente", "Cliente collegato", "Tipo Pratica", "Istituto",
    "Importo Richiesto", "Stato", "Priorità", "Responsabile pratica", "Data Apertura",
    "Scadenza", "Prossima azione", "Scadenza prossima azione", "Stato documentazione",
    "Completezza dossier", "Probabilità delibera", "Importo massimo stimato",
    "Alert e criticità", "Documenti mancanti", "Note",
]

DOCUMENT_FIELDS = [
    "Documento", "Cliente", "Cliente collegato", "Pratica ID", "Pratica collegata",
    "Tipo Documento", "Esercizio", "Data Documento", "Nome Originale",
    "Nome IA Suggerito", "Nome Definitivo", "Origine", "URL Drive", "Sintesi IA",
    "Stato Verifica", "SHA-256",
]

EMAIL_FIELDS = [
    "Oggetto", "Data e ora", "Mittente", "Cliente", "Cliente collegato", "Pratica ID",
    "Pratica collegata", "Sintesi IA", "Allegati", "Priorità", "Azione Richiesta",
    "Gestita", "Gmail Message ID",
]

ANALYSIS_FIELDS = [
    "Analisi ID", "Cliente", "Cliente collegato", "Pratica collegata", "Data Analisi",
    "Esercizio", "Ricavi", "EBITDA", "EBITDA Margin", "PFN", "PFN EBITDA", "DSCR",
    "Patrimonio Netto", "Score", "Rating", "Importo Sostenibile Min",
    "Importo Sostenibile Max", "Punti di Forza", "Criticità", "Raccomandazione IA",
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
        if value and all(isinstance(v, str) and v.startswith("rec") for v in value):
            return value
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


def set_flash(message: str, kind: str = "success") -> None:
    st.session_state["financeplus_flash"] = (kind, message)


def show_flash() -> None:
    flash = st.session_state.pop("financeplus_flash", None)
    if not flash:
        return
    kind, message = flash
    if kind == "error":
        st.error(message)
    elif kind == "warning":
        st.warning(message)
    else:
        st.success(message)


def is_missing(value: Any) -> bool:
    if value is None or value == "":
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    return False


def as_text(value: Any) -> str:
    return "" if is_missing(value) else str(value)


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if is_missing(value):
            return default
        return float(value)
    except Exception:
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        if is_missing(value):
            return default
        return int(float(value))
    except Exception:
        return default


def as_date(value: Any):
    if is_missing(value):
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def option_index(options: List[str], current: Any) -> int:
    current_text = as_text(current)
    try:
        return options.index(current_text)
    except ValueError:
        return 0


def age_days(value: Any) -> int | None:
    parsed = as_date(value)
    return None if parsed is None else (date.today() - parsed).days


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

Per usare anche modifica anagrafica e gestione pratiche, il token deve avere accesso **in lettura e scrittura** alla base **FinancePlus AI**. Non inserire mai il token nel codice GitHub.
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


def contains_record_id(value: Any, record_id: str) -> bool:
    if isinstance(value, list):
        return record_id in value
    if isinstance(value, str):
        return record_id in value
    return False


def related_rows(df: pd.DataFrame, client_record_id: str, client_name: str) -> pd.DataFrame:
    if df.empty:
        return df

    linked_mask = pd.Series(False, index=df.index)
    if "Cliente collegato" in df.columns:
        linked_mask = df["Cliente collegato"].apply(
            lambda value: contains_record_id(value, client_record_id)
        )

    text_mask = pd.Series(False, index=df.index)
    if "Cliente" in df.columns:
        text_mask = (
            df["Cliente"].fillna("").astype(str).str.strip().str.casefold()
            == str(client_name).strip().casefold()
        )

    return df.loc[linked_mask | text_mask].copy()


def visible_df(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    visible = [column for column in columns if column in df.columns]
    return df[visible].copy() if visible else pd.DataFrame()


def suggest_practice_id(client_name: str, practices: pd.DataFrame) -> str:
    slug = re.sub(r"[^A-Z0-9]+", "", client_name.upper())[:18] or "CLIENTE"
    year = date.today().year
    prefix = f"{slug}-{year}-"
    numbers: List[int] = []
    if not practices.empty and "Pratica ID" in practices.columns:
        for practice_id in practices["Pratica ID"].dropna().astype(str):
            if practice_id.startswith(prefix):
                tail = practice_id[len(prefix):]
                if tail.isdigit():
                    numbers.append(int(tail))
    next_number = max(numbers, default=0) + 1
    return f"{prefix}{next_number:03d}"


def update_client_record(
    token: str,
    base_id: str,
    record_id: str,
    fields: Dict[str, Any],
) -> None:
    client = AirtableClient(token=token, base_id=base_id)
    client.update_record(TABLES["Clienti"], record_id, fields)


def create_practice_record(token: str, base_id: str, fields: Dict[str, Any]) -> None:
    client = AirtableClient(token=token, base_id=base_id)
    client.create_record(TABLES["Pratiche"], fields)


def update_practice_record(
    token: str,
    base_id: str,
    record_id: str,
    fields: Dict[str, Any],
) -> None:
    client = AirtableClient(token=token, base_id=base_id)
    client.update_record(TABLES["Pratiche"], record_id, fields)


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
        view = clienti.loc[
            stale,
            ["Cliente", "Partita IVA", "Data estrazione visura", "Stato verifica anagrafica"],
        ].copy()
        if view.empty:
            st.success("Nessuna visura oltre 180 giorni.")
        else:
            st.dataframe(view, use_container_width=True, hide_index=True)

    with col_b:
        st.markdown("#### Pratiche aperte / in lavorazione")
        if pratiche.empty:
            st.info("Nessuna pratica disponibile.")
        else:
            view = pratiche[
                ["Pratica ID", "Cliente", "Stato", "Priorità", "Istituto", "Importo Richiesto"]
            ].copy()
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
    show_flash()
    clienti = load_df(token, base_id, TABLES["Clienti"], CLIENT_FIELDS)

    st.title("👥 Clienti")
    st.caption(
        f"{len(clienti)} anagrafiche Airtable. Cerca, consulta e aggiorna il cliente senza uscire da Streamlit."
    )

    q = st.text_input(
        "🔎 Cerca cliente",
        placeholder="Ragione sociale, P.IVA, CF, PEC, REA, comune, amministratore...",
    )

    f1, f2, f3 = st.columns(3)
    province = sorted([x for x in clienti["Provincia"].dropna().astype(str).unique() if x])
    states = sorted([x for x in clienti["Stato attività"].dropna().astype(str).unique() if x])
    checks = sorted(
        [x for x in clienti["Stato verifica anagrafica"].dropna().astype(str).unique() if x]
    )
    provincia = f1.selectbox("Provincia", ["Tutte"] + province)
    stato = f2.selectbox("Stato attività", ["Tutti"] + states)
    verifica = f3.selectbox("Verifica anagrafica", ["Tutte"] + checks)

    filtered = clienti.copy()
    if q:
        search_columns = [
            "Cliente", "Partita IVA", "Codice Fiscale", "PEC", "REA", "Comune",
            "Provincia", "ATECO", "Rappresentante/Amministratore",
        ]
        searchable = (
            filtered[search_columns]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
            .str.casefold()
        )
        filtered = filtered[searchable.str.contains(q.casefold(), regex=False)]
    if provincia != "Tutte":
        filtered = filtered[filtered["Provincia"] == provincia]
    if stato != "Tutti":
        filtered = filtered[filtered["Stato attività"] == stato]
    if verifica != "Tutte":
        filtered = filtered[filtered["Stato verifica anagrafica"] == verifica]

    st.caption(f"Risultati: {len(filtered)}")
    cols = [
        "Cliente", "Partita IVA", "PEC", "REA", "Comune", "Provincia", "ATECO",
        "Rappresentante/Amministratore", "Data estrazione visura", "Stato verifica anagrafica",
    ]
    st.dataframe(filtered[cols], use_container_width=True, hide_index=True)

    if filtered.empty:
        st.info("Nessun cliente corrisponde ai filtri impostati.")
        return

    st.divider()
    records = filtered.set_index("_record_id")
    record_ids = records.index.tolist()

    def client_label(record_id: str) -> str:
        client = records.loc[record_id]
        name = client.get("Cliente") or "Cliente senza nome"
        vat = client.get("Partita IVA") or "P.IVA n.d."
        return f"{name} · {vat}"

    selected_record_id = st.selectbox(
        "📂 Apri scheda cliente",
        record_ids,
        format_func=client_label,
        key="selected_client_record_id",
    )
    row = records.loc[selected_record_id]
    selected_name = str(row.get("Cliente") or "")

    all_pratiche = load_df(token, base_id, TABLES["Pratiche"], PRACTICE_FIELDS)
    pratiche = related_rows(all_pratiche, selected_record_id, selected_name)
    documenti = related_rows(
        load_df(token, base_id, TABLES["Documenti"], DOCUMENT_FIELDS),
        selected_record_id,
        selected_name,
    )
    email = related_rows(
        load_df(token, base_id, TABLES["Email"], EMAIL_FIELDS),
        selected_record_id,
        selected_name,
    )
    analisi = related_rows(
        load_df(token, base_id, TABLES["Analisi Creditizie"], ANALYSIS_FIELDS),
        selected_record_id,
        selected_name,
    )

    st.subheader(selected_name or "Scheda cliente")
    days = age_days(row.get("Data estrazione visura"))
    if days is not None and days > 180:
        st.warning(f"Visura da aggiornare: ultima estrazione {days} giorni fa.")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("P.IVA", row.get("Partita IVA") or "—")
    m2.metric("REA", row.get("REA") or "—")
    m3.metric("Rating", row.get("Rating FinancePlus") or "—")
    m4.metric("Pratiche", len(pratiche))
    m5.metric("Documenti", len(documenti))

    tab_anagrafica, tab_pratiche, tab_documenti, tab_email, tab_analisi = st.tabs(
        ["🏢 Anagrafica", "💼 Pratiche", "📄 Documenti", "✉️ Email", "📈 Analisi creditizie"]
    )

    with tab_anagrafica:
        left, right = st.columns(2)
        with left:
            st.markdown("#### Dati identificativi")
            st.write(f"**Ragione sociale:** {row.get('Cliente') or '—'}")
            st.write(f"**Partita IVA:** {row.get('Partita IVA') or '—'}")
            st.write(f"**Codice fiscale:** {row.get('Codice Fiscale') or '—'}")
            st.write(f"**PEC:** {row.get('PEC') or '—'}")
            st.write(f"**Email:** {row.get('Email') or '—'}")
            st.write(f"**Forma giuridica:** {row.get('Forma giuridica') or '—'}")
            st.write(f"**Stato attività:** {row.get('Stato attività') or '—'}")
            st.write(f"**Stato cliente:** {row.get('Stato Cliente') or '—'}")

        with right:
            st.markdown("#### Profilo camerale")
            st.write(f"**REA:** {row.get('REA') or '—'}")
            st.write(f"**Sede legale:** {row.get('Sede legale') or '—'}")
            st.write(
                f"**CAP / Comune / Provincia:** {row.get('CAP') or '—'} / "
                f"{row.get('Comune') or '—'} / {row.get('Provincia') or '—'}"
            )
            st.write(f"**ATECO:** {row.get('ATECO') or '—'}")
            st.write(f"**Attività prevalente:** {row.get('Attività prevalente') or '—'}")
            st.write(f"**Capitale sociale:** {format_currency(row.get('Capitale sociale EUR'))}")
            st.write(
                f"**Rappresentante / Amministratore:** "
                f"{row.get('Rappresentante/Amministratore') or '—'}"
            )

        st.markdown("#### Dossier FinancePlus")
        d1, d2, d3, d4 = st.columns(4)
        d1.write(f"**CR aggiornata al:** {row.get('CR aggiornata al') or '—'}")
        d2.write(f"**Ultimo bilancio:** {row.get('Ultimo bilancio disponibile') or '—'}")
        d3.write(f"**Ultima visura:** {row.get('Data estrazione visura') or '—'}")
        d4.write(f"**N. visure:** {row.get('N. visure presenti') or '—'}")
        st.write(f"**File sorgente visura:** {row.get('File sorgente visura') or '—'}")
        st.write(f"**Stato verifica anagrafica:** {row.get('Stato verifica anagrafica') or '—'}")
        if row.get("Note"):
            st.info(str(row.get("Note")))

        with st.expander("✏️ Modifica anagrafica cliente", expanded=False):
            st.caption("Le modifiche vengono salvate direttamente nella tabella Clienti di Airtable.")
            with st.form(f"edit_client_{selected_record_id}"):
                c1, c2 = st.columns(2)
                with c1:
                    edit_name = st.text_input("Ragione sociale", value=as_text(row.get("Cliente")))
                    edit_vat = st.text_input("Partita IVA", value=as_text(row.get("Partita IVA")))
                    edit_cf = st.text_input("Codice Fiscale", value=as_text(row.get("Codice Fiscale")))
                    edit_pec = st.text_input("PEC", value=as_text(row.get("PEC")))
                    edit_email = st.text_input("Email", value=as_text(row.get("Email")))
                    client_status_options = [""] + CLIENT_STATUSES
                    edit_client_status = st.selectbox(
                        "Stato Cliente",
                        client_status_options,
                        index=option_index(client_status_options, row.get("Stato Cliente")),
                    )
                    edit_rea = st.text_input("REA", value=as_text(row.get("REA")))
                    edit_form = st.text_input("Forma giuridica", value=as_text(row.get("Forma giuridica")))
                    edit_activity_status = st.text_input(
                        "Stato attività", value=as_text(row.get("Stato attività"))
                    )
                    edit_ateco = st.text_input("ATECO", value=as_text(row.get("ATECO")))
                with c2:
                    edit_address = st.text_area("Sede legale", value=as_text(row.get("Sede legale")))
                    edit_city = st.text_input("Comune", value=as_text(row.get("Comune")))
                    edit_province = st.text_input("Provincia", value=as_text(row.get("Provincia")))
                    edit_cap = st.text_input("CAP", value=as_text(row.get("CAP")))
                    edit_activity = st.text_area(
                        "Attività prevalente", value=as_text(row.get("Attività prevalente"))
                    )
                    edit_capital = st.number_input(
                        "Capitale sociale EUR",
                        min_value=0.0,
                        value=as_float(row.get("Capitale sociale EUR")),
                        step=1000.0,
                    )
                    edit_admin = st.text_input(
                        "Rappresentante / Amministratore",
                        value=as_text(row.get("Rappresentante/Amministratore")),
                    )
                    edit_visura_date = st.date_input(
                        "Data estrazione visura", value=as_date(row.get("Data estrazione visura"))
                    )
                    edit_visura_status = st.text_input(
                        "Stato verifica anagrafica",
                        value=as_text(row.get("Stato verifica anagrafica")),
                    )
                e1, e2, e3, e4 = st.columns(4)
                with e1:
                    edit_n_visure = st.number_input(
                        "N. visure presenti",
                        min_value=0,
                        value=as_int(row.get("N. visure presenti")),
                        step=1,
                    )
                with e2:
                    edit_cr_date = st.date_input(
                        "CR aggiornata al", value=as_date(row.get("CR aggiornata al"))
                    )
                with e3:
                    edit_last_balance = st.number_input(
                        "Ultimo bilancio disponibile",
                        min_value=0,
                        value=as_int(row.get("Ultimo bilancio disponibile")),
                        step=1,
                    )
                with e4:
                    edit_source = st.text_input(
                        "File sorgente visura", value=as_text(row.get("File sorgente visura"))
                    )
                edit_notes = st.text_area("Note", value=as_text(row.get("Note")), height=140)
                save_client = st.form_submit_button("💾 Salva anagrafica", use_container_width=True)

            if save_client:
                if not edit_name.strip():
                    st.error("La Ragione sociale non può essere vuota.")
                else:
                    fields: Dict[str, Any] = {
                        "Cliente": edit_name.strip(),
                        "Partita IVA": edit_vat.strip(),
                        "Codice Fiscale": edit_cf.strip(),
                        "PEC": edit_pec.strip(),
                        "Email": edit_email.strip(),
                        "Stato Cliente": edit_client_status or None,
                        "REA": edit_rea.strip(),
                        "Sede legale": edit_address.strip(),
                        "Comune": edit_city.strip(),
                        "Provincia": edit_province.strip(),
                        "CAP": edit_cap.strip(),
                        "Forma giuridica": edit_form.strip(),
                        "Stato attività": edit_activity_status.strip(),
                        "ATECO": edit_ateco.strip(),
                        "Attività prevalente": edit_activity.strip(),
                        "Capitale sociale EUR": edit_capital if edit_capital > 0 else None,
                        "Rappresentante/Amministratore": edit_admin.strip(),
                        "Data estrazione visura": edit_visura_date.isoformat() if edit_visura_date else None,
                        "N. visure presenti": edit_n_visure if edit_n_visure > 0 else None,
                        "File sorgente visura": edit_source.strip(),
                        "Stato verifica anagrafica": edit_visura_status.strip(),
                        "CR aggiornata al": edit_cr_date.isoformat() if edit_cr_date else None,
                        "Ultimo bilancio disponibile": edit_last_balance if edit_last_balance > 0 else None,
                        "Note": edit_notes.strip(),
                    }
                    try:
                        update_client_record(token, base_id, selected_record_id, fields)
                        set_flash(f"Anagrafica di {edit_name.strip()} aggiornata su Airtable.")
                        refresh()
                    except AirtableAPIError as exc:
                        st.error(f"Salvataggio non riuscito: {exc}")

    with tab_pratiche:
        st.caption(f"{len(pratiche)} pratiche collegate")
        if pratiche.empty:
            st.info("Nessuna pratica collegata a questo cliente.")
        else:
            st.dataframe(
                visible_df(
                    pratiche,
                    [
                        "Pratica ID", "Tipo Pratica", "Istituto", "Importo Richiesto", "Stato",
                        "Priorità", "Responsabile pratica", "Data Apertura", "Scadenza",
                        "Prossima azione", "Scadenza prossima azione", "Stato documentazione",
                        "Completezza dossier", "Probabilità delibera", "Importo massimo stimato",
                        "Alert e criticità", "Documenti mancanti",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("➕ Nuova pratica", expanded=pratiche.empty):
            suggested_id = suggest_practice_id(selected_name, pratiche)
            with st.form(f"new_practice_{selected_record_id}"):
                n1, n2, n3 = st.columns(3)
                with n1:
                    new_id = st.text_input("Pratica ID", value=suggested_id)
                    new_type = st.selectbox("Tipo pratica", PRACTICE_TYPES)
                    new_institute = st.text_input("Istituto / intermediario")
                with n2:
                    new_amount = st.number_input(
                        "Importo richiesto EUR", min_value=0.0, value=0.0, step=5000.0
                    )
                    new_status = st.selectbox("Stato", PRACTICE_STATUSES)
                    new_priority = st.selectbox("Priorità", PRACTICE_PRIORITIES, index=1)
                with n3:
                    new_owner = st.text_input("Responsabile pratica")
                    new_opened = st.date_input("Data apertura", value=date.today())
                    new_due = st.date_input("Scadenza", value=None)
                new_next_action = st.text_area("Prossima azione")
                new_next_due = st.date_input("Scadenza prossima azione", value=None)
                new_doc_status = st.selectbox("Stato documentazione", DOCUMENTATION_STATUSES)
                new_missing_docs = st.text_area("Documenti mancanti")
                new_alerts = st.text_area("Alert e criticità")
                new_notes = st.text_area("Note")
                create_practice = st.form_submit_button("➕ Crea pratica", use_container_width=True)

            if create_practice:
                if not new_id.strip():
                    st.error("Pratica ID obbligatorio.")
                else:
                    practice_fields: Dict[str, Any] = {
                        "Pratica ID": new_id.strip(),
                        "Cliente": selected_name,
                        "Cliente collegato": [selected_record_id],
                        "Tipo Pratica": new_type,
                        "Istituto": new_institute.strip(),
                        "Importo Richiesto": new_amount if new_amount > 0 else None,
                        "Stato": new_status,
                        "Priorità": new_priority,
                        "Responsabile pratica": new_owner.strip(),
                        "Data Apertura": new_opened.isoformat() if new_opened else None,
                        "Scadenza": new_due.isoformat() if new_due else None,
                        "Prossima azione": new_next_action.strip(),
                        "Scadenza prossima azione": new_next_due.isoformat() if new_next_due else None,
                        "Stato documentazione": new_doc_status,
                        "Alert e criticità": new_alerts.strip(),
                        "Documenti mancanti": new_missing_docs.strip(),
                        "Note": new_notes.strip(),
                    }
                    try:
                        create_practice_record(token, base_id, practice_fields)
                        set_flash(f"Pratica {new_id.strip()} creata e collegata a {selected_name}.")
                        refresh()
                    except AirtableAPIError as exc:
                        st.error(f"Creazione pratica non riuscita: {exc}")

        if not pratiche.empty:
            with st.expander("📝 Aggiorna pratica / prossima azione", expanded=False):
                practice_records = pratiche.set_index("_record_id")
                practice_record_ids = practice_records.index.tolist()

                def practice_label(record_id: str) -> str:
                    p = practice_records.loc[record_id]
                    return f"{p.get('Pratica ID') or record_id} · {p.get('Istituto') or 'Istituto n.d.'}"

                selected_practice_id = st.selectbox(
                    "Pratica da aggiornare",
                    practice_record_ids,
                    format_func=practice_label,
                    key=f"practice_edit_{selected_record_id}",
                )
                practice = practice_records.loc[selected_practice_id]

                with st.form(f"edit_practice_{selected_practice_id}"):
                    p1, p2, p3 = st.columns(3)
                    with p1:
                        edit_practice_status = st.selectbox(
                            "Stato",
                            PRACTICE_STATUSES,
                            index=option_index(PRACTICE_STATUSES, practice.get("Stato")),
                        )
                        edit_priority = st.selectbox(
                            "Priorità",
                            PRACTICE_PRIORITIES,
                            index=option_index(PRACTICE_PRIORITIES, practice.get("Priorità")),
                        )
                        edit_owner = st.text_input(
                            "Responsabile pratica", value=as_text(practice.get("Responsabile pratica"))
                        )
                    with p2:
                        edit_institute = st.text_input(
                            "Istituto", value=as_text(practice.get("Istituto"))
                        )
                        edit_amount = st.number_input(
                            "Importo richiesto EUR",
                            min_value=0.0,
                            value=as_float(practice.get("Importo Richiesto")),
                            step=5000.0,
                        )
                        edit_doc_status = st.selectbox(
                            "Stato documentazione",
                            DOCUMENTATION_STATUSES,
                            index=option_index(
                                DOCUMENTATION_STATUSES, practice.get("Stato documentazione")
                            ),
                        )
                    with p3:
                        edit_due = st.date_input("Scadenza", value=as_date(practice.get("Scadenza")))
                        edit_next_due = st.date_input(
                            "Scadenza prossima azione",
                            value=as_date(practice.get("Scadenza prossima azione")),
                        )
                    edit_next_action = st.text_area(
                        "Prossima azione", value=as_text(practice.get("Prossima azione"))
                    )
                    edit_missing_docs = st.text_area(
                        "Documenti mancanti", value=as_text(practice.get("Documenti mancanti"))
                    )
                    edit_alerts = st.text_area(
                        "Alert e criticità", value=as_text(practice.get("Alert e criticità"))
                    )
                    edit_practice_notes = st.text_area(
                        "Note pratica", value=as_text(practice.get("Note"))
                    )
                    save_practice = st.form_submit_button(
                        "💾 Salva aggiornamento pratica", use_container_width=True
                    )

                if save_practice:
                    practice_update_fields: Dict[str, Any] = {
                        "Stato": edit_practice_status,
                        "Priorità": edit_priority,
                        "Responsabile pratica": edit_owner.strip(),
                        "Istituto": edit_institute.strip(),
                        "Importo Richiesto": edit_amount if edit_amount > 0 else None,
                        "Scadenza": edit_due.isoformat() if edit_due else None,
                        "Prossima azione": edit_next_action.strip(),
                        "Scadenza prossima azione": edit_next_due.isoformat() if edit_next_due else None,
                        "Stato documentazione": edit_doc_status,
                        "Documenti mancanti": edit_missing_docs.strip(),
                        "Alert e criticità": edit_alerts.strip(),
                        "Note": edit_practice_notes.strip(),
                    }
                    try:
                        update_practice_record(
                            token, base_id, selected_practice_id, practice_update_fields
                        )
                        set_flash(
                            f"Pratica {practice.get('Pratica ID') or selected_practice_id} aggiornata su Airtable."
                        )
                        refresh()
                    except AirtableAPIError as exc:
                        st.error(f"Aggiornamento pratica non riuscito: {exc}")

    with tab_documenti:
        st.caption(f"{len(documenti)} documenti collegati")
        if documenti.empty:
            st.info("Nessun documento collegato a questo cliente.")
        else:
            docs_view = visible_df(
                documenti,
                [
                    "Documento", "Tipo Documento", "Esercizio", "Data Documento",
                    "Nome Definitivo", "Origine", "Stato Verifica", "URL Drive", "Sintesi IA",
                ],
            )
            st.dataframe(
                docs_view,
                use_container_width=True,
                hide_index=True,
                column_config={"URL Drive": st.column_config.LinkColumn("Apri su Drive")},
            )

    with tab_email:
        st.caption(f"{len(email)} email collegate")
        if email.empty:
            st.info("Nessuna email collegata a questo cliente.")
        else:
            email_view = email.copy()
            email_view["_sort_date"] = pd.to_datetime(email_view["Data e ora"], errors="coerce")
            email_view = email_view.sort_values("_sort_date", ascending=False)
            st.dataframe(
                visible_df(
                    email_view,
                    [
                        "Data e ora", "Mittente", "Oggetto", "Priorità", "Sintesi IA",
                        "Azione Richiesta", "Allegati", "Gestita",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
            )

    with tab_analisi:
        st.caption(f"{len(analisi)} analisi collegate")
        if analisi.empty:
            st.info("Nessuna analisi creditizia collegata a questo cliente.")
        else:
            analysis_view = analisi.copy()
            analysis_view["_sort_date"] = pd.to_datetime(
                analysis_view["Data Analisi"], errors="coerce"
            )
            analysis_view = analysis_view.sort_values("_sort_date", ascending=False)
            st.dataframe(
                visible_df(
                    analysis_view,
                    [
                        "Analisi ID", "Data Analisi", "Esercizio", "Ricavi", "EBITDA",
                        "EBITDA Margin", "PFN", "PFN EBITDA", "DSCR", "Patrimonio Netto",
                        "Score", "Rating", "Importo Sostenibile Min", "Importo Sostenibile Max",
                        "Punti di Forza", "Criticità", "Raccomandazione IA",
                    ],
                ),
                use_container_width=True,
                hide_index=True,
            )


def generic_page(token: str, base_id: str, title: str, fields: List[str]) -> None:
    df = load_df(token, base_id, TABLES[title], fields)
    st.title(title)
    st.caption(f"{len(df)} record")
    q = st.text_input("Ricerca", key=f"search_{title}")
    filtered = df.copy()
    if q:
        searchable = filtered.fillna("").astype(str).agg(" ".join, axis=1).str.casefold()
        filtered = filtered[searchable.str.contains(q.casefold(), regex=False)]
    visible = [
        c for c in fields if c in filtered.columns and c not in {"Cliente collegato", "Pratica collegata"}
    ]
    st.dataframe(filtered[visible], use_container_width=True, hide_index=True)


def main() -> None:
    token, base_id = connection_panel()
    with st.sidebar:
        page = st.radio(
            "Navigazione",
            ["Dashboard", "👥 Clienti", "Pratiche", "Documenti", "Email", "Analisi Creditizie"],
        )
        st.divider()
        st.caption(f"FinancePlus Airtable v{APP_VERSION}")

    if page == "Dashboard":
        dashboard(token, base_id)
    elif page == "👥 Clienti":
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
