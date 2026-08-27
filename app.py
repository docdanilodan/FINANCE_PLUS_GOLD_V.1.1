import os
import pandas as pd
import streamlit as st
from analytics_engine import FinancialInputs, analyze
from document_ai import classify_text, suggested_name
from modules.credit_risk import CRMonth, analyze_cr
from modules.bank_account import analyze_transactions
from modules.business_plan import BPInputs, project
from modules.dossier import build_dossier_markdown
from modules.client_documents_pdf import build_client_documents_pdf
from services.airtable_adapter import AirtableGold, DEFAULT_BASE_ID

st.set_page_config(page_title="FINANCE PLUS GOLD 3.2",page_icon="🏦",layout="wide")
st.title("FINANCE PLUS GOLD 3.2")
st.caption("Clienti Airtable • Document AI • Documenti PDF • Controllo pratiche • Centrale Rischi • Conti correnti • Business Plan • Dossier banca")

def _secret_or_env(name,default=""):
    try:value=st.secrets.get(name,"")
    except Exception:value=""
    return str(value or os.getenv(name,default) or "")
def _airtable_client():
    token=_secret_or_env("AIRTABLE_TOKEN")
    return AirtableGold(token=token,base_id=_secret_or_env("AIRTABLE_BASE_ID",DEFAULT_BASE_ID)) if token else None
def _records_to_df(records,preferred=None):
    rows=[]
    for record in records:
        row={"Record ID":record.get("id","")};row.update(record.get("fields",{}));rows.append(row)
    if not rows:return pd.DataFrame()
    df=pd.DataFrame(rows)
    if preferred:
        cols=[c for c in preferred if c in df.columns];df=df[cols+[c for c in df.columns if c not in cols]]
    return df
def _linked_count(fields,name):
    value=fields.get(name,[]);return len(value) if isinstance(value,list) else 0
def _safe_filename(value):return "".join(c if c.isalnum() or c in "-_" else "_" for c in value).strip("_") or "Cliente"

TABS=["Dashboard","👥 Clienti","Document AI","Analytics","Centrale Rischi","Conti Correnti","Business Plan","Dossier"]
tabs=st.tabs(TABS)
with tabs[0]:
    st.subheader("Centro di controllo GOLD");c1,c2,c3,c4=st.columns(4);c1.metric("CRM","Airtable reale");c2.metric("Document AI","Naming + verifica");c3.metric("Credito","Bilancio + CR + CC");c4.metric("Guardrail","No dati inventati")
with tabs[1]:
    st.subheader("👥 Anagrafica Clienti");st.caption("Scheda cliente, documenti caricati e PDF operativo con controllo pratiche.")
    airtable=_airtable_client()
    if airtable is None:st.warning("Airtable non autenticato. Configurare AIRTABLE_TOKEN nei Secrets.")
    else:
        try:clienti=airtable.list_records("clienti",max_records=1000)
        except Exception as exc:st.error(f"Impossibile leggere Airtable: {exc}");clienti=[]
        if clienti:
            query=st.text_input("🔎 Cerca cliente",placeholder="Ragione sociale, P.IVA, CF, PEC o REA",key="client_search").strip().casefold()
            def matches(record):
                f=record.get("fields",{});return not query or query in " ".join(str(f.get(k,"") or "") for k in ("Cliente","Partita IVA","Codice Fiscale","PEC","REA")).casefold()
            filtered=sorted([r for r in clienti if matches(r)],key=lambda r:str(r.get("fields",{}).get("Cliente","")).casefold())
            if filtered:
                labels={r["id"]:str(r.get("fields",{}).get("Cliente",r["id"])) for r in filtered};selected_id=st.selectbox("Seleziona cliente",[r["id"] for r in filtered],format_func=lambda rid:labels.get(rid,rid),key="client_selected");selected=next(r for r in filtered if r["id"]==selected_id);f=selected.get("fields",{});client_name=str(f.get("Cliente","Cliente"))
                st.divider();st.subheader(client_name);a,b,c,d=st.columns(4);a.metric("Pratiche",_linked_count(f,"Pratiche"));b.metric("Documenti",_linked_count(f,"Documenti"));c.metric("Email",_linked_count(f,"Email collegate"));d.metric("Analisi",_linked_count(f,"Analisi Creditizie"))
                col1,col2=st.columns(2)
                with col1:st.markdown("#### Identificazione");st.write(f"**P.IVA:** {f.get('Partita IVA','—')}");st.write(f"**CF:** {f.get('Codice Fiscale','—')}");st.write(f"**PEC:** {f.get('PEC','—')}");st.write(f"**REA:** {f.get('REA','—')}")
                with col2:st.markdown("#### Stato FinancePlus");st.write(f"**ATECO:** {f.get('ATECO','—')}");st.write(f"**Rating:** {f.get('Rating FinancePlus','—')}");st.write(f"**Ultimo bilancio:** {f.get('Ultimo bilancio disponibile','—')}");st.write(f"**CR aggiornata:** {f.get('CR aggiornata al','—')}")
                doc_ids=f.get("Documenti",[]);documents=airtable.get_records_by_ids("documenti",doc_ids,max_records=500) if isinstance(doc_ids,list) and doc_ids else []
                practice_ids=f.get("Pratiche",[]);practices=airtable.get_records_by_ids("pratiche",practice_ids,max_records=100) if isinstance(practice_ids,list) and practice_ids else []
                st.markdown("### 📚 Riepilogo documenti e controllo pratica");view_col,pdf_col=st.columns(2);show_docs=view_col.toggle("📋 Vedi riepilogo documenti",value=False,key=f"show_docs_{selected_id}")
                if documents:
                    pdf_bytes=build_client_documents_pdf(client_name,documents,practices);pdf_col.download_button("📄 Scarica PDF completo",data=pdf_bytes,file_name=f"{_safe_filename(client_name)}_Documenti_e_Controllo_Pratiche.pdf",mime="application/pdf",use_container_width=True,key=f"pdf_{selected_id}")
                else:pdf_col.button("📄 Nessun documento da scaricare",disabled=True,use_container_width=True,key=f"no_pdf_{selected_id}")
                if show_docs:
                    if documents:
                        preferred=["Documento","Tipo Documento","Esercizio","Data Documento","Nome Originale","Nome Definitivo","Origine","Stato Verifica","URL Drive"];ddf=_records_to_df(documents,preferred).drop(columns=["Record ID"],errors="ignore");st.dataframe(ddf,use_container_width=True,hide_index=True,column_config={"URL Drive":st.column_config.LinkColumn("Drive",display_text="Apri")})
                    else:st.info("Nessun documento collegato.")
                if practices:
                    with st.expander(f"⚙️ Controllo pratiche ({len(practices)})",expanded=True):
                        preferred=["Pratica ID","Tipo Pratica","Istituto","Importo Richiesto","Stato","Completezza dossier","Documenti mancanti","Alert e criticità","Prossima azione","Scadenza prossima azione","Responsabile pratica"];pdf=_records_to_df(practices,preferred).drop(columns=["Record ID"],errors="ignore");st.dataframe(pdf,use_container_width=True,hide_index=True)
                for field_name,table_key,preferred in [("Email collegate","email",["Oggetto","Data e ora","Mittente","Priorità","Azione Richiesta","Gestita"]),("Analisi Creditizie","analisi",["Analisi ID","Data Analisi","Esercizio","Score","Rating","DSCR","PFN EBITDA"])]:
                    ids=f.get(field_name,[])
                    if isinstance(ids,list) and ids:
                        with st.expander(f"{field_name} ({len(ids)})"):
                            rdf=_records_to_df(airtable.get_records_by_ids(table_key,ids,max_records=100),preferred)
                            if not rdf.empty:st.dataframe(rdf.drop(columns=["Record ID"],errors="ignore"),use_container_width=True,hide_index=True)
            else:st.info("Nessun cliente corrisponde alla ricerca.")
with tabs[2]:
    text=st.text_area("Testo estratto dal documento",height=220);company=st.text_input("Azienda / soggetto");year=st.number_input("Anno documento",0,2100,0)
    if st.button("Analizza documento"):r=classify_text(text);r.company_name=company;r.document_year=int(year) or None;st.json({"categoria":r.category,"confidenza":r.confidence,"nome_proposto":suggested_name(r)})
with tabs[3]:
    names=["revenue","ebitda","ebit","financial_debt","cash","equity","current_assets","current_liabilities","cfads","debt_service"];labels=["Ricavi","EBITDA","EBIT","Debiti finanziari","Cassa","Patrimonio netto","Attivo corrente","Passivo corrente","CFADS","Servizio debito"];values={}
    for n,label in zip(names,labels):
        raw=st.text_input(label,key=n)
        try:values[n]=float(raw.replace(".","").replace(",",".")) if raw.strip() else None
        except ValueError:values[n]=None
    if st.button("Calcola KPI e rating"):st.json(analyze(FinancialInputs(**values)).__dict__)
with tabs[4]:
    cr_file=st.file_uploader("CSV Centrale Rischi",type=["csv"],key="cr")
    if cr_file:
        df=pd.read_csv(cr_file);rows=[CRMonth(str(r.get("month","")),float(r.get("granted",0) or 0),float(r.get("used",0) or 0),float(r.get("past_due",0) or 0),float(r.get("bad_debt",0) or 0)) for _,r in df.iterrows()];st.json(analyze_cr(rows))
with tabs[5]:
    cc_file=st.file_uploader("CSV movimenti conto",type=["csv"],key="cc")
    if cc_file:st.json(analyze_transactions(pd.read_csv(cc_file)))
with tabs[6]:
    base=st.number_input("Ricavi base",min_value=0.0);growth=st.number_input("Crescita ricavi %",value=5.0)/100;margin=st.number_input("EBITDA margin %",value=15.0)/100
    if st.button("Proietta 5 anni"):st.dataframe(pd.DataFrame(project(BPInputs(base,growth,margin))))
with tabs[7]:
    name=st.text_input("Cliente dossier");vat=st.text_input("P.IVA dossier")
    if st.button("Genera bozza dossier"):
        md=build_dossier_markdown({"Cliente":name,"Partita IVA":vat});st.markdown(md);st.download_button("Scarica dossier Markdown",md,file_name="FinancePlus_GOLD_Dossier.md")
