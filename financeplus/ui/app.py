from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from financeplus import APP_NAME, __version__
from financeplus.config import settings
from financeplus.db import init_schema, session_scope, Repository
from financeplus.audit import audit
from financeplus.storage import LocalStorage
from financeplus.usecases import ingest_document
from financeplus.engines.finance import FinancialInputs, analyze_financials, maximum_financeable, compute_phantom, evaluate_mcc
from financeplus.engines.cashflow import parse_statement, normalize_transactions, analyze_cashflow
from financeplus.engines.business_plan import BusinessPlanAssumptions, project_business_plan
from financeplus.engines.matcher import rank_operators
from financeplus.domain import OperatorProfile

NAVY="#0B1F3A"; COPPER="#C46B32"; BG="#F4F6F9"

def _theme():
    st.markdown(f"""<style>.stApp{{background:{BG}}}[data-testid='stSidebar']{{background:{NAVY}}}[data-testid='stSidebar'] *{{color:white!important}}h1,h2,h3{{color:{NAVY}}}.fp-status{{border-left:4px solid {COPPER};padding:.4rem .8rem;background:white}}</style>""",unsafe_allow_html=True)

def _obj_rows(items):
    rows=[]
    for x in items:
        d={k:v for k,v in vars(x).items() if not k.startswith('_sa_')}
        rows.append(d)
    return rows

def page_dashboard():
    st.subheader("Centro di controllo MASTER")
    with session_scope() as s:
        counts=Repository(s).counts()
    cols=st.columns(5)
    for c,(k,label) in zip(cols,[("clients","Clienti"),("practices","Pratiche"),("documents","Documenti"),("events","CRM/Eventi"),("analyses","Analisi")]): c.metric(label,counts[k])
    st.markdown("### Stato architettura")
    rows=[{"Modulo":"Single app.py","Stato":"IMPLEMENTATO"},{"Modulo":"DB primary","Stato":"PostgreSQL/Neon" if settings.production_database else "SQLite fallback"},{"Modulo":"CR 36m","Stato":"TESTATO SU 3 CR REALI / regressione attiva"},{"Modulo":"Cashflow","Stato":"TESTATO SU 3 E/C REALI / riconciliazione OK"},{"Modulo":"PHANTOM","Stato":"RICHIEDE SORGENTE ORIGINALE + CALIBRAZIONE"},{"Modulo":"MCC","Stato":"RICHIEDE RULESET"},{"Modulo":"Matcher Top20","Stato":"RICHIEDE CATALOGO SORGENTE"}]
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    st.info("Pipeline MASTER: cliente/pratica → documenti → Document AI → CR/CC/KPI → BP/PHANTOM/MCC/Matcher → report; nessun indicatore viene inventato quando mancano dati o ruleset.")

def page_clients():
    st.subheader("Cliente 360")
    query=st.text_input("Cerca cliente")
    with session_scope() as s:
        repo=Repository(s); clients=repo.list_clients(query)
        st.dataframe(pd.DataFrame(_obj_rows(clients)),use_container_width=True,hide_index=True)
        with st.expander("Nuovo cliente"):
            with st.form("new_client"):
                name=st.text_input("Ragione sociale"); vat=st.text_input("P.IVA"); cf=st.text_input("Codice fiscale"); pec=st.text_input("PEC"); rea=st.text_input("REA"); ateco=st.text_input("ATECO"); save=st.form_submit_button("Salva")
            if save:
                obj,created=repo.create_client(legal_name=name,vat=vat,tax_code=cf,pec=pec,rea=rea,ateco=ateco); audit(s,"CLIENT_CREATE" if created else "CLIENT_DEDUP",entity_type="client",entity_id=obj.id); st.success("Cliente creato." if created else "Cliente già esistente: nessun duplicato creato.")

def page_practices():
    st.subheader("Pratiche")
    with session_scope() as s:
        repo=Repository(s); clients=repo.list_clients(); practices=repo.list_practices(); st.dataframe(pd.DataFrame(_obj_rows(practices)),use_container_width=True,hide_index=True)
        if clients:
            labels={c.id:c.legal_name for c in clients}
            with st.expander("Nuova pratica"):
                with st.form("new_practice"):
                    cid=st.selectbox("Cliente",list(labels),format_func=lambda x:labels[x]); code=st.text_input("Pratica ID"); typ=st.selectbox("Tipo",["Finanziamento","Factoring","Leasing","Fideiussione","Altro"]); inst=st.text_input("Istituto"); amount=st.number_input("Importo richiesto",min_value=0.0); status=st.selectbox("Stato",["Da avviare","In istruttoria","Integrazione","Deliberata","Erogata","Respinta","Sospesa"]); owner=st.text_input("Responsabile"); ok=st.form_submit_button("Crea")
                if ok:
                    p=repo.create_practice(client_id=cid,code=code,practice_type=typ,institution=inst,requested_amount=amount,status=status,owner=owner); audit(s,"PRACTICE_CREATE",entity_type="practice",entity_id=p.id); st.success("Pratica creata.")

def page_documents():
    st.subheader("Archivio documentale")
    with session_scope() as s:
        repo=Repository(s); docs=repo.list_documents(); clients=repo.list_clients(); st.dataframe(pd.DataFrame(_obj_rows(docs)),use_container_width=True,hide_index=True)
        upload=st.file_uploader("Carica documento")
        if upload:
            labels={0:"Non associato"}|{c.id:c.legal_name for c in clients}; cid=st.selectbox("Cliente",list(labels),format_func=lambda x:labels[x]); category=st.selectbox("Categoria",["Bilancio","Bozza","Situazione contabile","Centrale Rischi","Estratto conto","Visura","Fattura","Contratto","Presentazione aziendale","Altro"])
            if st.button("Archivia",type="primary"):
                row,created=ingest_document(s,repo,LocalStorage(settings.local_storage_dir/"documents"),data=upload.getvalue(),filename=upload.name,client_id=cid or None,category=category,actor="streamlit"); st.success("Archiviato." if created else "Duplicato SHA-256: nessuna seconda copia creata.")

def page_document_ai():
    st.subheader("Document AI / OCR-IDP")
    st.caption("Rule-first: classificazione deterministica prima dei provider esterni. Le scansioni pure richiedono OCR/IDP e quality gate.")
    upload=st.file_uploader("Documento da classificare",key="doc_ai_upload")
    pasted=st.text_area("Testo aggiuntivo / OCR esterno",key="doc_ai_text")
    if upload and st.button("Classifica documento"):
        try:
            from document_ai import classify_text, suggested_name
            raw=upload.getvalue(); ext=Path(upload.name).suffix.lower(); text=pasted
            if ext in {".txt",".csv",".md",".json",".xml"}: text=raw.decode("utf-8",errors="replace")+"\n"+pasted
            elif ext==".pdf":
                try:
                    from pypdf import PdfReader
                    import io
                    text="\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)+"\n"+pasted
                except Exception as exc: st.warning(f"PDF non testuale o non leggibile: {exc}")
            c=classify_text((upload.name+"\n"+text)[:120000])
            st.json({"category":c.category,"confidence":c.confidence,"company":getattr(c,"company_name",None),"year":getattr(c,"document_year",None),"suggested_name":suggested_name(c,upload.name)})
            if not text.strip(): st.warning("Nessun testo estratto: RICHIEDE OCR/IDP o verifica umana.")
        except Exception as exc: st.error(f"Document AI non disponibile: {exc}")

def page_finance():
    st.subheader("Bilanci / KPI / Rating baseline")
    cols=st.columns(3)
    vals={}
    for c,key,label in [(cols[0],"revenue","Ricavi"),(cols[1],"ebitda","EBITDA"),(cols[2],"ebit","EBIT"),(cols[0],"financial_debt","Debito finanziario"),(cols[1],"cash","Cassa"),(cols[2],"equity","Patrimonio netto"),(cols[0],"current_assets","Attivo corrente"),(cols[1],"current_liabilities","Passivo corrente"),(cols[2],"total_assets","Totale attivo"),(cols[0],"cfads","CFADS"),(cols[0],"debt_service","Debt service"),(cols[1],"interest_expense","Oneri finanziari"),(cols[2],"cfo","CFO")]: vals[key]=c.number_input(label,value=None,placeholder="N/D")
    if st.button("Calcola analisi"):
        r=analyze_financials(FinancialInputs(**vals)); st.json({"data_quality":r.data_quality,"metrics":r.metrics,"score":r.score,"rating":r.rating,"semaphore":r.semaphore,"warnings":r.warnings}); st.session_state["last_finance"]={"inputs":vals,"result":r.__dict__}
        if vals.get("cfads"):
            st.write("**Massimo finanziabile DSCR-constrained:**",maximum_financeable(vals["cfads"]))

def page_cr():
    st.subheader("Centrale Rischi avanzata — fino a 36 mesi")
    st.caption("Motore canonico: financeplus_cr_engine / CR_2026_2_CORRETTO.")
    f=st.file_uploader("Carica CR (PDF/TXT/CSV/XLS/XLSX)",key="cr_upload")
    if f and st.button("Analizza CR"):
        import tempfile
        from financeplus.engines.cr import analyze_cr_file, availability
        st.write(availability())
        suffix=Path(f.name).suffix
        with tempfile.TemporaryDirectory() as td:
            inp=Path(td)/("input"+suffix); out=Path(td)/"REPORT_CR.pdf"; audit_path=Path(td)/"audit.json"
            inp.write_bytes(f.getvalue())
            try:
                result=analyze_cr_file(str(inp),str(out),str(audit_path))
                payload=result.to_dict() if hasattr(result,"to_dict") else str(result)
                st.json(payload)
                if out.exists(): st.download_button("Scarica Report CR PDF",out.read_bytes(),"REPORT_CR.pdf","application/pdf")
            except Exception as exc: st.error(f"Analisi CR non riuscita: {exc}")

def page_cashflow():
    st.subheader("Conti correnti e Cash Flow")
    st.caption("Parser MASTER Stage2: testato su 3 estratti conto reali con layout differenti; riconciliazione saldo iniziale + movimenti = saldo finale riuscita sui 3 campioni.")
    f=st.file_uploader("Estratto conto",key="cc_file")
    opening=st.number_input("Saldo iniziale (facoltativo)",value=None,placeholder="N/D")
    if f and st.button("Analizza E/C"):
        raw=parse_statement(f.name,f.getvalue()); tx=normalize_transactions(raw); result=analyze_cashflow(tx,opening_balance=opening); st.dataframe(tx.head(500),use_container_width=True); st.json(result)

def page_bp():
    st.subheader("Business Plan 5 anni — MASTER fallback verificabile")
    st.warning("La sorgente BPlan_Manager_Premium_Bancario_360.py non è stata recuperata integralmente. Questo engine usa assunzioni esplicite e non pretende parità 1:1 con il Premium 360.")
    c1,c2,c3=st.columns(3)
    a=BusinessPlanAssumptions(base_revenue=c1.number_input("Ricavi base",min_value=0.0,value=1000000.0),revenue_growth=c2.number_input("Crescita annua",value=0.05),ebitda_margin=c3.number_input("EBITDA margin",value=0.15),tax_rate=c1.number_input("Tax rate",value=0.24),annual_capex=c2.number_input("CAPEX annuo",value=50000.0),nwc_pct_revenue=c3.number_input("CCN % ricavi",value=0.10),loan_amount=c1.number_input("Nuovo finanziamento",value=0.0),annual_interest_rate=c2.number_input("Tasso annuo",value=0.06),loan_years=int(c3.number_input("Durata anni",min_value=1,value=5)),depreciation_years=int(c1.number_input("Ammortamento CAPEX anni",min_value=1,value=5)))
    if st.button("Genera BP"):
        df=pd.DataFrame(project_business_plan(a,5)); st.dataframe(df,use_container_width=True,hide_index=True); st.line_chart(df.set_index("year")[["revenue","ebitda","cfads","ending_debt"]])

def page_phantom_mcc():
    st.subheader("PHANTOM / PD / MCC")
    st.info("PHANTOM: il manuale recuperato conferma score 0-100, rating AAA-D e PD indicativa, ma i pesi originali non sono disponibili. MCC: ruleset completo non recuperato. Il MASTER blocca output inventati.")
    st.write(compute_phantom({"financial":80,"payments":70}).__dict__)
    st.write(evaluate_mcc({}).__dict__)

def page_matcher():
    st.subheader("Banche / Fintech / Factor / Confidi — Ranking operatori")
    st.warning("Il manuale Credit Matcher conferma 28 operatori e Top 20, ma il catalogo/pesi sorgente non è materialmente disponibile. Caricare un catalogo JSON approvato per attivare il ranking.")
    f=st.file_uploader("Catalogo operatori JSON",type=["json"],key="matcher_catalog")
    if f:
        payload=json.loads(f.getvalue().decode("utf-8")); ops=[OperatorProfile(**x) for x in payload]; feature_json=st.text_area("Feature pratica JSON",value='{"dscr": 75, "leverage": 70, "liquidity": 65}')
        if st.button("Calcola Top 20"):
            st.dataframe(pd.DataFrame(rank_operators(json.loads(feature_json),ops)),use_container_width=True,hide_index=True)

def page_crm():
    st.subheader("CRM — Note, Call, Video Call, Appuntamenti")
    from financeplus.crm import create_event
    with session_scope() as s:
        repo=Repository(s); clients=repo.list_clients(); events=repo.list_events(); st.dataframe(pd.DataFrame(_obj_rows(events)),use_container_width=True,hide_index=True)
        labels={0:"Nessun cliente"}|{c.id:c.legal_name for c in clients}
        with st.form("crm_event"):
            cid=st.selectbox("Cliente",list(labels),format_func=lambda x:labels[x]); typ=st.selectbox("Tipo",["Nota","Call","Video Call","Appuntamento"]); institution=st.text_input("Banca/Istituto"); amount=st.number_input("Importo",min_value=0.0); instrument=st.selectbox("Strumento",["CHIRO","FACTORING","INVOICE","MUTUO","PRESTITO","CROWD","ALTRO"]); subject=st.text_input("Oggetto"); details=st.text_area("Dettagli"); status=st.selectbox("Stato",["EVASA","INEVASA","IN ATTESA"]); ok=st.form_submit_button("Salva evento")
        if ok:
            e=create_event(s,client_id=cid or None,event_type=typ,institution=institution,amount=amount or None,instrument=instrument,subject=subject,details=details,status=status); audit(s,"CRM_EVENT_CREATE",entity_type="crm_event",entity_id=e.id); st.success("Evento salvato.")

def page_integrations():
    st.subheader("Integrazioni")
    st.dataframe(pd.DataFrame([{"Integrazione":k,"Stato":v} for k,v in settings.integration_status().items()]),use_container_width=True,hide_index=True)
    st.caption("Gmail/Aruba/Airtable/Drive restano collegati agli adapter correnti del repository. OneDrive è predisposto tramite StoragePort ma richiede implementazione/credenziali E2E.")

def page_mandates():
    st.subheader("Mandati e compensi")
    st.caption("Baseline deterministica dal modulo corrente; storico/PDF-DOCX completo richiede recupero della fonte FinancePlus Mandati.")
    try:
        from modules.mandate import MandateInputs, calculate_mandate
        c1,c2,c3=st.columns(3)
        req=c1.number_input("Importo richiesto",min_value=0.0); appr=c2.number_input("Importo approvato",min_value=0.0); pct=c3.number_input("% compenso",min_value=0.0,value=0.0)/100
        fixed=c1.number_input("Fisso",min_value=0.0); vat=c2.number_input("IVA %",min_value=0.0,value=0.0)/100; wh=c3.number_input("Ritenuta %",min_value=0.0,value=0.0)/100
        if st.button("Calcola mandato"): st.json(calculate_mandate(MandateInputs(req,appr,pct,fixed,vat,wh)))
    except Exception as exc: st.error(str(exc))

def page_reports():
    st.subheader("Report / Dossier")
    st.info("I generatori storici `FinancePlus_Airtable/client_fascicolo.py`, `modules/client_documents_pdf.py` e `modules/pdf_dossier.py` restano disponibili nel repository. La migrazione a un unico report engine condiviso è DA MIGLIORARE dopo visual regression.")
    if "last_finance" in st.session_state:
        st.json(st.session_state["last_finance"])
    else: st.caption("Eseguire prima una analisi KPI per vedere l'ultimo risultato di sessione.")

def page_settings():
    st.subheader("Impostazioni / Provenienza / Audit")
    st.code(f"Environment: {settings.environment}\nDatabase: {'PostgreSQL/Neon' if settings.production_database else 'SQLite fallback'}\nStorage: {settings.local_storage_dir}")
    st.write(f"**Build:** APP_NUOVA_SETT_IA_00 MASTER {__version__}")
    st.write("**Regola PD:** PHANTOM PD resta 'indicativa' finché non calibrata e validata.")
    st.write("**Original sources:** manifest immutabile + hash/blob refs; le fonti non recuperabili sono marcate RICHIEDE SORGENTE ORIGINALE.")

def run_app():
    st.set_page_config(page_title=APP_NAME,page_icon="FP",layout="wide",initial_sidebar_state="expanded"); _theme(); init_schema()
    with st.sidebar:
        st.markdown("## FINANCEPLUS\n**MASTER APP_NUOVA_SETT_IA_00**"); st.caption(__version__)
        pages={"Dashboard":page_dashboard,"Clienti 360":page_clients,"Pratiche":page_practices,"Documenti":page_documents,"Document AI":page_document_ai,"Bilanci/KPI":page_finance,"Centrale Rischi":page_cr,"Conti Correnti":page_cashflow,"Business Plan":page_bp,"PHANTOM / MCC":page_phantom_mcc,"Ranking operatori":page_matcher,"CRM Agenda":page_crm,"Mandati":page_mandates,"Report / Dossier":page_reports,"Email / Storage / API":page_integrations,"Impostazioni":page_settings}
        choice=st.radio("Navigazione",list(pages),label_visibility="collapsed")
    st.title(APP_NAME)
    pages[choice]()
