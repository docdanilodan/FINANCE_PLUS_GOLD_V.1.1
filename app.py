import streamlit as st
import pandas as pd
from analytics_engine import FinancialInputs, analyze
from document_ai import classify_text, suggested_name
from modules.credit_risk import CRMonth, analyze_cr
from modules.bank_account import analyze_transactions
from modules.business_plan import BPInputs, project
from modules.dossier import build_dossier_markdown

st.set_page_config(page_title='FINANCE PLUS GOLD 2.0', page_icon='🏦', layout='wide')
st.title('FINANCE PLUS GOLD 2.0')
st.caption('Document AI • Airtable CRM • Centrale Rischi • Conti correnti • Business Plan • Dossier banca')

tabs=st.tabs(['Dashboard','Document AI','Analytics','Centrale Rischi','Conti Correnti','Business Plan','Dossier'])
with tabs[0]:
    st.subheader('Centro di controllo GOLD')
    c1,c2,c3,c4=st.columns(4)
    c1.metric('CRM','Airtable reale'); c2.metric('Document AI','Naming + verifica'); c3.metric('Credito','Bilancio + CR + CC'); c4.metric('Guardrail','No dati inventati')
    st.info('Airtable FinancePlus AI verificato: Clienti, Pratiche, Documenti, Email e Analisi Creditizie. Le API esterne usano esclusivamente Secrets/variabili ambiente.')
with tabs[1]:
    text=st.text_area('Testo estratto dal documento', height=220); company=st.text_input('Azienda / soggetto'); year=st.number_input('Anno documento',0,2100,0)
    if st.button('Analizza documento'):
        r=classify_text(text); r.company_name=company; r.document_year=int(year) or None
        st.json({'categoria':r.category,'confidenza':r.confidence,'nome_proposto':suggested_name(r)})
with tabs[2]:
    names=['revenue','ebitda','ebit','financial_debt','cash','equity','current_assets','current_liabilities','cfads','debt_service']
    labels=['Ricavi','EBITDA','EBIT','Debiti finanziari','Cassa','Patrimonio netto','Attivo corrente','Passivo corrente','CFADS','Servizio debito']; values={}
    for n,l in zip(names,labels):
        raw=st.text_input(l,key=n); 
        try: values[n]=float(raw.replace('.','').replace(',','.')) if raw.strip() else None
        except ValueError: values[n]=None
    if st.button('Calcola KPI e rating'):
        result=analyze(FinancialInputs(**values)); st.json(result.__dict__)
with tabs[3]:
    st.write('Carica CSV con colonne: month, granted, used, past_due, bad_debt.')
    f=st.file_uploader('CSV Centrale Rischi',type=['csv'],key='cr')
    if f:
        df=pd.read_csv(f); rows=[CRMonth(str(r.get('month','')),float(r.get('granted',0) or 0),float(r.get('used',0) or 0),float(r.get('past_due',0) or 0),float(r.get('bad_debt',0) or 0)) for _,r in df.iterrows()]; st.json(analyze_cr(rows))
with tabs[4]:
    st.write('Carica CSV con almeno date e amount; importi positivi=entrate, negativi=uscite.')
    f=st.file_uploader('CSV movimenti conto',type=['csv'],key='cc')
    if f: st.json(analyze_transactions(pd.read_csv(f)))
with tabs[5]:
    base=st.number_input('Ricavi base',min_value=0.0); growth=st.number_input('Crescita ricavi %',value=5.0)/100; margin=st.number_input('EBITDA margin %',value=15.0)/100
    if st.button('Proietta 5 anni'): st.dataframe(pd.DataFrame(project(BPInputs(base,growth,margin))))
with tabs[6]:
    name=st.text_input('Cliente dossier'); vat=st.text_input('P.IVA dossier')
    if st.button('Genera bozza dossier'):
        md=build_dossier_markdown({'Cliente':name,'Partita IVA':vat}); st.markdown(md); st.download_button('Scarica dossier Markdown',md,file_name='FinancePlus_GOLD_Dossier.md')
