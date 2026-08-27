import os

import pandas as pd
import streamlit as st

from analytics_engine import FinancialInputs, analyze
from document_ai import classify_text, suggested_name
from modules.credit_risk import CRMonth, analyze_cr
from modules.bank_account import analyze_transactions
from modules.business_plan import BPInputs, project
from modules.dossier import build_dossier_markdown
from services.airtable_adapter import AirtableGold, DEFAULT_BASE_ID


st.set_page_config(page_title="FINANCE PLUS GOLD 3.1", page_icon="🏦", layout="wide")
st.title("FINANCE PLUS GOLD 3.1")
st.caption(
    "Clienti Airtable • Document AI • Centrale Rischi • Conti correnti • "
    "Business Plan • Dossier banca"
)


def _secret_or_env(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default) or "")


def _airtable_client():
    token = _secret_or_env("AIRTABLE_TOKEN")
    if not token:
        return None
    base_id = _secret_or_env("AIRTABLE_BASE_ID", DEFAULT_BASE_ID)
    return AirtableGold(token=token, base_id=base_id)


def _records_to_df(records: list[dict], preferred: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for record in records:
        row = {"Record ID": record.get("id", "")}
        row.update(record.get("fields", {}))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if preferred:
        cols = [c for c in preferred if c in df.columns]
        rest = [c for c in df.columns if c not in cols]
        df = df[cols + rest]
    return df


def _linked_count(fields: dict, name: str) -> int:
    value = fields.get(name, [])
    return len(value) if isinstance(value, list) else 0


TABS = [
    "Dashboard",
    "👥 Clienti",
    "Document AI",
    "Analytics",
    "Centrale Rischi",
    "Conti Correnti",
    "Business Plan",
    "Dossier",
]
tabs = st.tabs(TABS)

with tabs[0]:
    st.subheader("Centro di controllo GOLD")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("CRM", "Airtable reale")
    c2.metric("Document AI", "Naming + verifica")
    c3.metric("Credito", "Bilancio + CR + CC")
    c4.metric("Guardrail", "No dati inventati")
    st.info(
        "Airtable FinancePlus AI: Clienti, Pratiche, Documenti, Email e Analisi Creditizie. "
        "Le credenziali esterne sono lette solo da Streamlit Secrets/variabili ambiente."
    )

with tabs[1]:
    st.subheader("👥 Anagrafica Clienti")
    st.caption("Cerca un cliente e apri la scheda completa sincronizzata con Airtable FinancePlus AI.")

    airtable = _airtable_client()
    if airtable is None:
        st.warning(
            "Airtable non è ancora autenticato in questo deploy. In Streamlit → Settings → Secrets "
            "aggiungi AIRTABLE_TOKEN e, facoltativamente, AIRTABLE_BASE_ID."
        )
        st.code('AIRTABLE_TOKEN = "pat_..."\nAIRTABLE_BASE_ID = "appoNJtS64JIcZUhT"', language="toml")
    else:
        try:
            clienti = airtable.list_records("clienti", max_records=1000)
        except Exception as exc:
            st.error(f"Impossibile leggere Airtable: {exc}")
            clienti = []

        if clienti:
            st.metric("Clienti presenti", len(clienti))
            query = st.text_input(
                "🔎 Cerca cliente",
                placeholder="Ragione sociale, P.IVA, CF, PEC o REA",
                key="client_search",
            ).strip().casefold()

            def matches(record: dict) -> bool:
                if not query:
                    return True
                fields = record.get("fields", {})
                haystack = " ".join(
                    str(fields.get(k, "") or "")
                    for k in ("Cliente", "Partita IVA", "Codice Fiscale", "PEC", "REA")
                ).casefold()
                return query in haystack

            filtered = [r for r in clienti if matches(r)]
            filtered.sort(key=lambda r: str(r.get("fields", {}).get("Cliente", "")).casefold())
            st.caption(f"Risultati: {len(filtered)}")

            if not filtered:
                st.info("Nessun cliente corrisponde alla ricerca.")
            else:
                labels = {
                    r["id"]: str(r.get("fields", {}).get("Cliente", r["id"]))
                    for r in filtered
                }
                selected_id = st.selectbox(
                    "Seleziona cliente",
                    options=[r["id"] for r in filtered],
                    format_func=lambda rid: labels.get(rid, rid),
                    key="client_selected",
                )
                selected = next(r for r in filtered if r["id"] == selected_id)
                f = selected.get("fields", {})

                st.divider()
                st.subheader(str(f.get("Cliente", "Cliente")))

                a, b, c, d = st.columns(4)
                a.metric("Pratiche", _linked_count(f, "Pratiche"))
                b.metric("Documenti", _linked_count(f, "Documenti"))
                c.metric("Email", _linked_count(f, "Email collegate"))
                d.metric("Analisi creditizie", _linked_count(f, "Analisi Creditizie"))

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("#### Identificazione")
                    st.write(f"**Partita IVA:** {f.get('Partita IVA', '—')}")
                    st.write(f"**Codice Fiscale:** {f.get('Codice Fiscale', '—')}")
                    st.write(f"**PEC:** {f.get('PEC', '—')}")
                    st.write(f"**REA:** {f.get('REA', '—')}")
                    st.write(f"**Forma giuridica:** {f.get('Forma giuridica', '—')}")
                    st.write(f"**Stato attività:** {f.get('Stato attività', '—')}")

                with col2:
                    st.markdown("#### Sede e attività")
                    st.write(f"**Sede legale:** {f.get('Sede legale', '—')}")
                    st.write(f"**Comune:** {f.get('Comune', '—')}")
                    st.write(f"**Provincia:** {f.get('Provincia', '—')}")
                    st.write(f"**CAP:** {f.get('CAP', '—')}")
                    st.write(f"**ATECO:** {f.get('ATECO', '—')}")
                    st.write(f"**Attività prevalente:** {f.get('Attività prevalente', '—')}")

                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("#### Governance e visura")
                    st.write(f"**Amministratore:** {f.get('Rappresentante/Amministratore', '—')}")
                    capitale = f.get("Capitale sociale EUR")
                    if isinstance(capitale, (int, float)):
                        st.write(f"**Capitale sociale:** € {capitale:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    else:
                        st.write("**Capitale sociale:** —")
                    st.write(f"**Data ultima visura:** {f.get('Data estrazione visura', '—')}")
                    st.write(f"**N. visure presenti:** {f.get('N. visure presenti', '—')}")
                    st.write(f"**File sorgente:** {f.get('File sorgente visura', '—')}")
                    st.write(f"**Verifica anagrafica:** {f.get('Stato verifica anagrafica', '—')}")

                with col4:
                    st.markdown("#### Stato FinancePlus")
                    st.write(f"**Stato cliente:** {f.get('Stato Cliente', '—')}")
                    st.write(f"**Rating FinancePlus:** {f.get('Rating FinancePlus', '—')}")
                    st.write(f"**CR aggiornata al:** {f.get('CR aggiornata al', '—')}")
                    st.write(f"**Ultimo bilancio:** {f.get('Ultimo bilancio disponibile', '—')}")
                    if f.get("Cartella Drive"):
                        st.link_button("📁 Apri cartella Drive", f["Cartella Drive"])

                linked_sections = [
                    ("Pratiche", "pratiche", ["Pratica ID", "Tipo Pratica", "Istituto", "Importo Richiesto", "Stato", "Priorità", "Prossima azione"]),
                    ("Documenti", "documenti", ["Documento", "Tipo Documento", "Esercizio", "Data Documento", "Nome Definitivo", "Stato Verifica", "URL Drive"]),
                    ("Email collegate", "email", ["Oggetto", "Data e ora", "Mittente", "Priorità", "Azione Richiesta", "Gestita"]),
                    ("Analisi Creditizie", "analisi", ["Analisi ID", "Data Analisi", "Esercizio", "Score", "Rating", "DSCR", "PFN EBITDA"]),
                ]
                for field_name, table_key, preferred in linked_sections:
                    ids = f.get(field_name, [])
                    if isinstance(ids, list) and ids:
                        with st.expander(f"{field_name} ({len(ids)})"):
                            related = airtable.get_records_by_ids(table_key, ids, max_records=100)
                            rdf = _records_to_df(related, preferred)
                            if rdf.empty:
                                st.info("Nessun dettaglio disponibile.")
                            else:
                                st.dataframe(rdf.drop(columns=["Record ID"], errors="ignore"), use_container_width=True, hide_index=True)
        else:
            st.info("La tabella Clienti non contiene record o non è leggibile.")

with tabs[2]:
    text = st.text_area("Testo estratto dal documento", height=220)
    company = st.text_input("Azienda / soggetto")
    year = st.number_input("Anno documento", 0, 2100, 0)
    if st.button("Analizza documento"):
        r = classify_text(text)
        r.company_name = company
        r.document_year = int(year) or None
        st.json({"categoria": r.category, "confidenza": r.confidence, "nome_proposto": suggested_name(r)})

with tabs[3]:
    names = [
        "revenue", "ebitda", "ebit", "financial_debt", "cash", "equity",
        "current_assets", "current_liabilities", "cfads", "debt_service",
    ]
    labels = [
        "Ricavi", "EBITDA", "EBIT", "Debiti finanziari", "Cassa", "Patrimonio netto",
        "Attivo corrente", "Passivo corrente", "CFADS", "Servizio debito",
    ]
    values = {}
    for n, label in zip(names, labels):
        raw = st.text_input(label, key=n)
        try:
            values[n] = float(raw.replace(".", "").replace(",", ".")) if raw.strip() else None
        except ValueError:
            values[n] = None
    if st.button("Calcola KPI e rating"):
        result = analyze(FinancialInputs(**values))
        st.json(result.__dict__)

with tabs[4]:
    st.write("Carica CSV con colonne: month, granted, used, past_due, bad_debt.")
    cr_file = st.file_uploader("CSV Centrale Rischi", type=["csv"], key="cr")
    if cr_file:
        df = pd.read_csv(cr_file)
        rows = [
            CRMonth(
                str(r.get("month", "")),
                float(r.get("granted", 0) or 0),
                float(r.get("used", 0) or 0),
                float(r.get("past_due", 0) or 0),
                float(r.get("bad_debt", 0) or 0),
            )
            for _, r in df.iterrows()
        ]
        st.json(analyze_cr(rows))

with tabs[5]:
    st.write("Carica CSV con almeno date e amount; importi positivi=entrate, negativi=uscite.")
    cc_file = st.file_uploader("CSV movimenti conto", type=["csv"], key="cc")
    if cc_file:
        st.json(analyze_transactions(pd.read_csv(cc_file)))

with tabs[6]:
    base = st.number_input("Ricavi base", min_value=0.0)
    growth = st.number_input("Crescita ricavi %", value=5.0) / 100
    margin = st.number_input("EBITDA margin %", value=15.0) / 100
    if st.button("Proietta 5 anni"):
        st.dataframe(pd.DataFrame(project(BPInputs(base, growth, margin))))

with tabs[7]:
    name = st.text_input("Cliente dossier")
    vat = st.text_input("P.IVA dossier")
    if st.button("Genera bozza dossier"):
        md = build_dossier_markdown({"Cliente": name, "Partita IVA": vat})
        st.markdown(md)
        st.download_button("Scarica dossier Markdown", md, file_name="FinancePlus_GOLD_Dossier.md")
