from __future__ import annotations

import hashlib
import io
import os
import re
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st
from pypdf import PdfReader

from analytics_engine import FinancialInputs, analyze
from document_ai import classify_text, suggested_name
from modules.bank_account import analyze_transactions
from modules.business_plan import BPInputs, project
from modules.client_documents_pdf import build_client_documents_pdf
from modules.credit_risk import CRMonth, analyze_cr
from modules.dossier import build_dossier_markdown
from modules.mandate import MandateInputs, calculate_mandate
from modules.pdf_dossier import build_pdf as build_dossier_pdf
from modules.smart_archive_ui import render_smart_archive
from services.airtable_adapter import AirtableGold, DEFAULT_BASE_ID
from services.gmail_drive_pipeline import sync_gmail_attachments
from FinancePlus_Airtable.client_fascicolo import build_client_fascicolo_pdf, safe_fascicolo_filename

APP_NAME = "FINANCE_PLUS_UNICO V_1.0"

st.set_page_config(page_title=APP_NAME, page_icon="🏦", layout="wide")


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


def records_df(records: list[dict], preferred: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for record in records or []:
        row = {"Record ID": record.get("id", "")}
        row.update(record.get("fields", {}))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    if preferred:
        first = [c for c in preferred if c in df.columns]
        df = df[first + [c for c in df.columns if c not in first]]
    return df


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "Cliente")).strip("_") or "Cliente"


def norm_company(value: str) -> str:
    s = str(value or "").upper().replace("&", " E ")
    for old, new in {
        "SOCIETA' A RESPONSABILITA' LIMITATA": "SRL",
        "SOCIETA A RESPONSABILITA LIMITATA": "SRL",
        "SOCIETA' PER AZIONI": "SPA",
        "SOCIETA PER AZIONI": "SPA",
        "S.R.L.S.": "SRLS",
        "S.R.L.": "SRL",
        "S.P.A.": "SPA",
    }.items():
        s = s.replace(old, new)
    s = re.sub(r"\bUNIPERSONALE\b", "", s)
    s = re.sub(r"[^A-Z0-9]+", "", s)
    for suffix in ("SRLS", "SRL", "SPA"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s


def client_documents(db: AirtableGold, client_name: str, linked_ids: Any) -> list[dict]:
    linked = db.get_records_by_ids("documenti", linked_ids, max_records=1000) if isinstance(linked_ids, list) else []
    try:
        all_docs = db.list_records("documenti", max_records=5000)
    except Exception:
        all_docs = []
    target = norm_company(client_name)
    by_name = [r for r in all_docs if target and norm_company(r.get("fields", {}).get("Cliente", "")) == target]
    merged = {}
    for record in linked + by_name:
        fields = record.get("fields", {})
        key = fields.get("SHA-256") or record.get("id") or fields.get("Documento")
        merged[str(key)] = record
    return list(merged.values())


def linked_records(db: AirtableGold, fields: dict, field_name: str, table: str, limit: int = 1000) -> list[dict]:
    ids = fields.get(field_name, [])
    return db.get_records_by_ids(table, ids, max_records=limit) if isinstance(ids, list) and ids else []


def to_float(raw: Any) -> float | None:
    text = str(raw or "").strip().replace("€", "").replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def money(value: Any) -> str:
    try:
        return f"€ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "—"


def extract_text(uploaded) -> tuple[str, str]:
    raw = uploaded.getvalue()
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join((page.extract_text() or "") for page in reader.pages), ""
        except Exception as exc:
            return "", f"PDF non leggibile: {exc}"
    if ext in {".txt", ".csv", ".md"}:
        return raw.decode("utf-8", errors="replace"), ""
    return "", "Formato non estratto automaticamente."


def google_profiles() -> dict[str, str]:
    profiles = {}
    primary = secret("GOOGLE_OAUTH_TOKEN_JSON")
    if primary:
        profiles["PRINCIPALE"] = primary
    try:
        keys = list(st.secrets.keys())
    except Exception:
        keys = []
    prefix = "GOOGLE_OAUTH_TOKEN_JSON_"
    for key in keys:
        if str(key).startswith(prefix):
            value = secret(str(key))
            if value:
                profiles[str(key)[len(prefix):] or str(key)] = value
    return profiles


def set_google_profile(token_json: str) -> None:
    os.environ["GOOGLE_OAUTH_TOKEN_JSON"] = token_json


def next_practice_code(client_name: str, practices: list[dict]) -> str:
    base = re.sub(r"[^A-Z0-9]", "", client_name.upper())[:10] or "CLIENTE"
    return f"{base}-{datetime.now().year}-{len(practices)+1:03d}"


DB = airtable_client()
PROFILES = google_profiles()

st.title(f"🏦 {APP_NAME}")
st.caption("CRM Airtable • Gmail/Drive • Document AI • Archivio Smart • Analytics • CR • Conti correnti • Business Plan • Dossier • Mandati")

with st.sidebar:
    st.markdown("### F_P_UNICO")
    st.caption("App master consolidata")
    st.write("✅ Airtable" if DB else "⚠️ Airtable da configurare")
    st.write("✅ Gmail/Drive" if PROFILES else "⚠️ Gmail/Drive da configurare")
    st.write("✅ Data Quality Gate")
    st.divider()
    page = st.radio(
        "Menu",
        ["🏠 Dashboard", "👥 Clienti", "🗂️ Archivio Smart", "🤖 Document AI", "✉️ Gmail & Drive", "📊 Analytics", "🏦 Centrale Rischi", "💳 Conti Correnti", "📈 Business Plan", "📄 Dossier Banca", "📝 Mandati"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Secrets e token non vengono salvati su GitHub.")


if page == "🏠 Dashboard":
    st.subheader("Centro di controllo operativo")
    if not DB:
        st.warning("Configura AIRTABLE_TOKEN nei Secrets per attivare il CRM reale.")
    else:
        try:
            clients = DB.list_records("clienti", max_records=5000)
            practices = DB.list_records("pratiche", max_records=5000)
            documents = DB.list_records("documenti", max_records=5000)
            emails = DB.list_records("email", max_records=5000)
            analyses = DB.list_records("analisi", max_records=5000)
        except Exception as exc:
            st.error(f"Errore Airtable: {exc}")
            clients, practices, documents, emails, analyses = [], [], [], [], []
        cols = st.columns(5)
        for col, label, value in zip(cols, ["Clienti", "Pratiche", "Documenti", "Email", "Analisi"], [len(clients), len(practices), len(documents), len(emails), len(analyses)]):
            col.metric(label, value)
        pdf = records_df(practices)
        if not pdf.empty:
            mask = pd.Series(False, index=pdf.index)
            if "Stato documentazione" in pdf.columns:
                mask |= ~pdf["Stato documentazione"].fillna("").astype(str).str.casefold().eq("completa")
            if "Documenti mancanti" in pdf.columns:
                mask |= pdf["Documenti mancanti"].fillna("").astype(str).str.strip().ne("")
            if "Alert e criticità" in pdf.columns:
                mask |= pdf["Alert e criticità"].fillna("").astype(str).str.strip().ne("")
            watch = pdf.loc[mask]
            st.markdown("### ⚠️ Pratiche da presidiare")
            if watch.empty:
                st.success("Nessuna criticità documentale rilevata nei campi disponibili.")
            else:
                wanted = [c for c in ["Pratica ID", "Cliente", "Istituto", "Stato", "Priorità", "Completezza dossier", "Documenti mancanti", "Prossima azione", "Scadenza prossima azione", "Alert e criticità"] if c in watch.columns]
                st.dataframe(watch[wanted].head(100), use_container_width=True, hide_index=True)
        edf = records_df(emails)
        if not edf.empty and "Priorità" in edf.columns:
            urgent = edf[edf["Priorità"].fillna("").astype(str).str.casefold().isin(["alta", "urgente", "critica"])]
            if not urgent.empty:
                st.markdown("### ✉️ Email prioritarie")
                wanted = [c for c in ["Data e ora", "Cliente", "Mittente", "Oggetto", "Priorità", "Azione Richiesta", "Gestita"] if c in urgent.columns]
                st.dataframe(urgent[wanted].head(50), use_container_width=True, hide_index=True)
    st.info("Pipeline unica: Gmail/Upload/Cellulare → Archivio Smart + Document AI → SHA-256 → Drive → Airtable → Analytics + CR + CC → Business Plan → Dossier/Fascicolo Cliente")


elif page == "👥 Clienti":
    st.subheader("👥 Clienti, pratiche e fascicolo completo")
    if not DB:
        st.warning("Airtable non autenticato.")
    else:
        try:
            clients = DB.list_records("clienti", max_records=5000)
        except Exception as exc:
            st.error(str(exc)); clients = []
        query = st.text_input("🔎 Cerca cliente", placeholder="Ragione sociale, P.IVA, CF, PEC, REA, Comune, ATECO").strip().casefold()
        filtered = []
        for record in clients:
            f = record.get("fields", {})
            corpus = " ".join(str(f.get(k, "") or "") for k in ("Cliente", "Partita IVA", "Codice Fiscale", "PEC", "REA", "Comune", "Provincia", "ATECO", "Rappresentante/Amministratore"))
            if not query or query in corpus.casefold():
                filtered.append(record)
        filtered.sort(key=lambda r: str(r.get("fields", {}).get("Cliente", "")).casefold())
        if not filtered:
            st.info("Nessun cliente trovato.")
        else:
            labels = {r["id"]: str(r.get("fields", {}).get("Cliente", r["id"])) for r in filtered}
            rid = st.selectbox("Seleziona cliente", list(labels), format_func=lambda x: labels[x])
            record = next(r for r in filtered if r["id"] == rid)
            f = record.get("fields", {})
            name = str(f.get("Cliente", "Cliente"))
            docs = client_documents(DB, name, f.get("Documenti", []))
            practices = linked_records(DB, f, "Pratiche", "pratiche", 500)
            emails = linked_records(DB, f, "Email collegate", "email", 1000)
            analyses = linked_records(DB, f, "Analisi Creditizie", "analisi", 500)
            st.divider(); st.subheader(name)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Pratiche", len(practices)); c2.metric("Documenti", len(docs)); c3.metric("Email", len(emails)); c4.metric("Analisi", len(analyses))
            tabs = st.tabs(["🏢 Anagrafica", "💼 Pratiche", "📄 Documenti", "✉️ Email", "📈 Analisi", "📁 PDF Cliente"])
            with tabs[0]:
                a, b = st.columns(2)
                with a:
                    for label, key in [("P.IVA", "Partita IVA"), ("CF", "Codice Fiscale"), ("PEC", "PEC"), ("REA", "REA"), ("Forma giuridica", "Forma giuridica"), ("Sede", "Sede legale")]:
                        st.write(f"**{label}:** {f.get(key, '—')}")
                with b:
                    for label, key in [("ATECO", "ATECO"), ("Attività", "Attività prevalente"), ("Amministratore", "Rappresentante/Amministratore"), ("Ultimo bilancio", "Ultimo bilancio disponibile"), ("CR aggiornata", "CR aggiornata al"), ("Rating", "Rating FinancePlus")]:
                        st.write(f"**{label}:** {f.get(key, '—')}")
                with st.expander("✏️ Modifica anagrafica"):
                    with st.form(f"edit_{rid}"):
                        new_name = st.text_input("Ragione sociale", value=str(f.get("Cliente", "") or ""))
                        vat = st.text_input("P.IVA", value=str(f.get("Partita IVA", "") or ""))
                        cf = st.text_input("CF", value=str(f.get("Codice Fiscale", "") or ""))
                        pec = st.text_input("PEC", value=str(f.get("PEC", "") or ""))
                        rea = st.text_input("REA", value=str(f.get("REA", "") or ""))
                        seat = st.text_input("Sede legale", value=str(f.get("Sede legale", "") or ""))
                        ateco = st.text_input("ATECO", value=str(f.get("ATECO", "") or ""))
                        notes = st.text_area("Note", value=str(f.get("Note", "") or ""))
                        save = st.form_submit_button("💾 Salva", use_container_width=True)
                    if save:
                        try:
                            DB.update_record("clienti", rid, {"Cliente": new_name, "Partita IVA": vat, "Codice Fiscale": cf, "PEC": pec, "REA": rea, "Sede legale": seat, "ATECO": ateco, "Note": notes})
                            st.success("Anagrafica aggiornata.")
                        except Exception as exc:
                            st.error(f"Aggiornamento non riuscito: {exc}")
            with tabs[1]:
                if practices:
                    wanted = ["Pratica ID", "Tipo Pratica", "Istituto", "Importo Richiesto", "Stato", "Priorità", "Responsabile pratica", "Completezza dossier", "Stato documentazione", "Documenti mancanti", "Prossima azione", "Scadenza prossima azione", "Alert e criticità"]
                    st.dataframe(records_df(practices, wanted).drop(columns=["Record ID"], errors="ignore"), use_container_width=True, hide_index=True)
                else:
                    st.info("Nessuna pratica collegata.")
                with st.expander("➕ Nuova pratica"):
                    with st.form(f"practice_{rid}"):
                        code = st.text_input("Pratica ID", value=next_practice_code(name, practices))
                        ptype = st.selectbox("Tipo", ["Finanziamento", "Factoring", "Leasing", "Fideiussione", "Altro"])
                        bank = st.text_input("Banca / intermediario")
                        amount = st.number_input("Importo richiesto €", min_value=0.0, step=1000.0)
                        status = st.selectbox("Stato", ["Da avviare", "In istruttoria", "Integrazione", "Deliberata", "Erogata", "Respinta", "Sospesa"])
                        priority = st.selectbox("Priorità", ["Alta", "Media", "Bassa"], index=1)
                        owner = st.text_input("Responsabile")
                        action = st.text_input("Prossima azione")
                        due = st.date_input("Scadenza prossima azione", value=date.today())
                        missing = st.text_area("Documenti mancanti")
                        create = st.form_submit_button("Crea pratica", use_container_width=True)
                    if create:
                        try:
                            DB.create_record("pratiche", {"Pratica ID": code, "Cliente": name, "Cliente collegato": [rid], "Tipo Pratica": ptype, "Istituto": bank, "Importo Richiesto": amount, "Stato": status, "Priorità": priority, "Responsabile pratica": owner, "Prossima azione": action, "Scadenza prossima azione": due.isoformat(), "Documenti mancanti": missing, "Stato documentazione": "Incompleta" if missing.strip() else "Da verificare"})
                            st.success("Pratica creata.")
                        except Exception as exc:
                            st.error(f"Creazione non riuscita: {exc}")
            with tabs[2]:
                if docs:
                    wanted = ["Documento", "Tipo Documento", "Esercizio", "Data Documento", "Pratica ID", "Nome Originale", "Nome Definitivo", "Origine", "Stato Verifica", "URL Drive", "Archivio ZIP sorgente", "Percorso nel pacchetto"]
                    ddf = records_df(docs, wanted).drop(columns=["Record ID"], errors="ignore")
                    st.dataframe(ddf, use_container_width=True, hide_index=True, column_config={"URL Drive": st.column_config.LinkColumn("Drive", display_text="Apri"), "Archivio ZIP sorgente": st.column_config.LinkColumn("ZIP", display_text="Apri")})
                else:
                    st.info("Nessun documento collegato.")
            with tabs[3]:
                if emails:
                    wanted = ["Data e ora", "Mittente", "Oggetto", "Priorità", "Azione Richiesta", "Allegati", "Gestita", "Sintesi IA"]
                    st.dataframe(records_df(emails, wanted).drop(columns=["Record ID"], errors="ignore"), use_container_width=True, hide_index=True)
                else:
                    st.info("Nessuna email collegata.")
            with tabs[4]:
                if analyses:
                    wanted = ["Data Analisi", "Esercizio", "Ricavi", "EBITDA", "PFN", "PFN EBITDA", "DSCR", "Score", "Rating", "Importo Sostenibile Min", "Importo Sostenibile Max", "Punti di Forza", "Criticità", "Raccomandazioni"]
                    st.dataframe(records_df(analyses, wanted).drop(columns=["Record ID"], errors="ignore"), use_container_width=True, hide_index=True)
                else:
                    st.info("Nessuna analisi collegata.")
            with tabs[5]:
                a, b = st.columns(2)
                if docs:
                    report = build_client_documents_pdf(name, docs, practices, f)
                    a.download_button("📄 Report documenti + pratiche", report, f"{safe_filename(name)}_Report_Cliente.pdf", "application/pdf", use_container_width=True)
                else:
                    a.button("📄 Nessun documento", disabled=True, use_container_width=True)
                fascicolo = build_client_fascicolo_pdf(f, records_df(docs).drop(columns=["Record ID"], errors="ignore"), records_df(practices).drop(columns=["Record ID"], errors="ignore"), records_df(emails).drop(columns=["Record ID"], errors="ignore"), records_df(analyses).drop(columns=["Record ID"], errors="ignore"))
                filename = safe_fascicolo_filename(name).replace("F_P_GOLD", "F_P_UNICO")
                b.download_button("📁 Fascicolo Cliente completo", fascicolo, filename, "application/pdf", use_container_width=True)


elif page == "🗂️ Archivio Smart":
    render_smart_archive(DB, PROFILES, secret)


elif page == "🤖 Document AI":
    st.subheader("🤖 Document AI — riconoscimento, naming e SHA-256")
    uploads = st.file_uploader("Carica PDF/TXT/CSV", type=["pdf", "txt", "csv", "md"], accept_multiple_files=True)
    pasted = st.text_area("Testo aggiuntivo / incollato", height=130)
    company = st.text_input("Azienda / soggetto (opzionale)")
    year = st.number_input("Anno (opzionale)", 0, 2100, 0)
    if st.button("Analizza", type="primary"):
        rows = []
        source = uploads or ([None] if pasted.strip() else [])
        for uploaded in source:
            if uploaded is None:
                filename, text, warning, sha, ext = "testo_incollato.txt", pasted, "", "—", ".txt"
            else:
                filename = uploaded.name
                text, warning = extract_text(uploaded)
                text = (text + "\n" + pasted).strip()
                sha = hashlib.sha256(uploaded.getvalue()).hexdigest()
                ext = os.path.splitext(filename)[1] or ".bin"
            result = classify_text((filename + "\n" + text)[:120000])
            if company.strip(): result.company_name = company.strip()
            if int(year): result.document_year = int(year)
            rows.append({"File": filename, "Categoria": result.category, "Confidenza": result.confidence, "Soggetto": result.company_name or "—", "Anno": result.document_year or "—", "Nome proposto": suggested_name(result, extension=ext), "SHA-256": sha, "Nota": warning})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.info("I dati non leggibili restano da verificare: nessuna ricostruzione arbitraria.")


elif page == "✉️ Gmail & Drive":
    st.subheader("✉️ Gmail → Document AI → Drive → Airtable")
    st.caption("Supporta più profili Google se aggiungi Secrets GOOGLE_OAUTH_TOKEN_JSON_<NOME>.")
    if not DB: st.warning("Serve AIRTABLE_TOKEN.")
    if not PROFILES: st.warning("Serve almeno un GOOGLE_OAUTH_TOKEN_JSON.")
    profile = st.selectbox("Profilo Google", list(PROFILES) if PROFILES else ["Non configurato"])
    query = st.text_input("Query Gmail", value="has:attachment newer_than:1d -in:spam -in:trash")
    folder = st.text_input("Drive folder ID", value=secret("GOOGLE_DRIVE_FOLDER_ID"))
    max_messages = st.slider("Messaggi massimi", 1, 200, 50)
    if st.button("🔄 Sincronizza", type="primary", disabled=not (DB and PROFILES)):
        try:
            set_google_profile(PROFILES[profile])
            result = sync_gmail_attachments(query=query, drive_folder_id=folder or None, max_messages=max_messages)
            a, b, c, d = st.columns(4)
            a.metric("Messaggi", result.get("messages", 0)); b.metric("Allegati", result.get("attachments", 0)); c.metric("Caricati", result.get("uploaded", 0)); d.metric("Duplicati", result.get("duplicates", 0))
            if result.get("errors"): st.warning(f"Errori: {len(result['errors'])}"); st.json(result["errors"])
            else: st.success("Sincronizzazione completata.")
        except Exception as exc:
            st.error(f"Sincronizzazione non riuscita: {exc}")


elif page == "📊 Analytics":
    st.subheader("📊 FinancePlus Analytics Engine")
    labels = [("revenue", "Ricavi"), ("ebitda", "EBITDA"), ("ebit", "EBIT"), ("financial_debt", "Debiti finanziari"), ("cash", "Cassa"), ("equity", "Patrimonio netto"), ("current_assets", "Attivo corrente"), ("current_liabilities", "Passivo corrente"), ("cfads", "CFADS"), ("debt_service", "Servizio del debito")]
    values = {}; cols = st.columns(2)
    for i, (key, label) in enumerate(labels): values[key] = to_float(cols[i % 2].text_input(label, key=f"a_{key}"))
    if st.button("Calcola KPI e rating", type="primary"):
        result = analyze(FinancialInputs(**values)); st.session_state["last_analysis"] = result.__dict__
        a, b, c, d = st.columns(4)
        a.metric("Data Quality", f"{result.data_quality}%"); b.metric("Score", result.score if result.score is not None else "N/D"); c.metric("Rating", result.rating); d.metric("Semaforo", result.semaphore)
        st.json(result.__dict__)


elif page == "🏦 Centrale Rischi":
    st.subheader("🏦 Centrale Rischi multi-mese")
    st.caption("CSV: month, granted, used, past_due, bad_debt")
    uploaded = st.file_uploader("CSV Centrale Rischi", type=["csv"])
    if uploaded:
        try:
            df = pd.read_csv(uploaded)
            rows = [CRMonth(str(r.get("month", "")), float(r.get("granted", 0) or 0), float(r.get("used", 0) or 0), float(r.get("past_due", 0) or 0), float(r.get("bad_debt", 0) or 0)) for _, r in df.iterrows()]
            result = analyze_cr(rows); st.session_state["last_cr"] = result; st.json(result)
        except Exception as exc: st.error(str(exc))


elif page == "💳 Conti Correnti":
    st.subheader("💳 Conti correnti e cash-flow")
    st.caption("CSV: date, amount. Positivo = entrata; negativo = uscita.")
    uploaded = st.file_uploader("CSV movimenti", type=["csv"])
    if uploaded:
        try:
            result = analyze_transactions(pd.read_csv(uploaded)); st.session_state["last_bank"] = result; st.json(result)
        except Exception as exc: st.error(str(exc))


elif page == "📈 Business Plan":
    st.subheader("📈 Business Plan a 5 anni")
    a, b, c = st.columns(3)
    base = a.number_input("Ricavi base €", min_value=0.0, step=10000.0)
    growth = b.number_input("Crescita ricavi %", value=5.0, step=0.5) / 100
    margin = c.number_input("EBITDA margin %", value=15.0, step=0.5) / 100
    a, b, c = st.columns(3)
    tax = a.number_input("Tax rate proxy %", value=24.0, step=0.5) / 100
    capex = b.number_input("CAPEX €", min_value=0.0, step=10000.0)
    wc = c.number_input("Capitale circolante %", value=10.0, step=0.5) / 100
    if st.button("Proietta 5 anni", type="primary"):
        result = project(BPInputs(base, growth, margin, tax, capex, wc)); df = pd.DataFrame(result); st.session_state["last_bp"] = result
        st.dataframe(df, use_container_width=True, hide_index=True); st.download_button("⬇️ CSV", df.to_csv(index=False).encode(), "Business_Plan_5_anni.csv", "text/csv")


elif page == "📄 Dossier Banca":
    st.subheader("📄 Dossier banca PDF + Markdown")
    client = {}
    if DB:
        try: clients = DB.list_records("clienti", max_records=5000)
        except Exception: clients = []
        labels = {r["id"]: str(r.get("fields", {}).get("Cliente", r["id"])) for r in clients}
        rid = st.selectbox("Cliente Airtable", [""] + list(labels), format_func=lambda x: "— Seleziona —" if not x else labels[x])
        if rid: client = next(r for r in clients if r["id"] == rid).get("fields", {}).copy()
    if not client:
        client = {"Cliente": st.text_input("Cliente"), "Partita IVA": st.text_input("P.IVA"), "PEC": st.text_input("PEC"), "ATECO": st.text_input("ATECO"), "Sede legale": st.text_input("Sede")}
    if st.button("Genera dossier", type="primary"):
        analysis_data = st.session_state.get("last_analysis", {}); cr_data = st.session_state.get("last_cr", {}); bank_data = st.session_state.get("last_bank", {})
        md = build_dossier_markdown(client, analysis_data, cr_data, bank_data); pdf = build_dossier_pdf(client, analysis_data, cr_data, bank_data)
        st.markdown(md); base = safe_filename(client.get("Cliente", "Cliente")); a, b = st.columns(2)
        a.download_button("📄 PDF", pdf, f"{base}_Dossier_F_P_UNICO.pdf", "application/pdf", use_container_width=True); b.download_button("📝 Markdown", md, f"{base}_Dossier_F_P_UNICO.md", "text/markdown", use_container_width=True)


elif page == "📝 Mandati":
    st.subheader("📝 Mandati — calcolo compenso")
    st.caption("Aliquote e ritenuta sono sempre input espliciti dell'utente.")
    a, b = st.columns(2); client = a.text_input("Cliente"); practice = b.text_input("Pratica / banca")
    a, b, c = st.columns(3); requested = a.number_input("Richiesto €", min_value=0.0, step=1000.0); approved = b.number_input("Deliberato/erogato €", min_value=0.0, step=1000.0); fee_pct = c.number_input("Compenso %", min_value=0.0, value=2.0, step=0.1)
    a, b, c = st.columns(3); fixed = a.number_input("Compenso fisso €", min_value=0.0, step=100.0); vat = b.number_input("IVA %", min_value=0.0, value=22.0, step=1.0); withholding = c.number_input("Ritenuta %", min_value=0.0, value=0.0, step=1.0)
    if st.button("Calcola mandato", type="primary"):
        result = calculate_mandate(MandateInputs(requested, approved, fee_pct / 100, fixed, vat / 100, withholding / 100)); row = {"Data": datetime.now().strftime("%d/%m/%Y %H:%M"), "Cliente": client, "Pratica": practice, **result}; st.session_state.setdefault("mandate_history", []).append(row)
        a, b, c = st.columns(3); a.metric("Base", money(result["fee_base"])); b.metric("Imponibile", money(result["taxable_fee"])); c.metric("Totale da incassare", money(result["total_due"]))
    history = st.session_state.get("mandate_history", [])
    if history:
        df = pd.DataFrame(history); st.dataframe(df, use_container_width=True, hide_index=True); st.download_button("⬇️ Storico CSV", df.to_csv(index=False).encode(), "Mandati_F_P_UNICO.csv", "text/csv")

st.divider()
st.caption("FINANCE_PLUS_UNICO V_1.0 • Un solo entrypoint • Nessun dato finanziario ricostruito senza fonte sufficiente")
