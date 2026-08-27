import streamlit as st
from analytics_engine import FinancialInputs, analyze
from document_ai import classify_text, suggested_name

st.set_page_config(page_title='FINANCE PLUS GOLD', page_icon='🏦', layout='wide')
st.title('FINANCE PLUS GOLD')
st.caption('Document AI • CRM • Mail/Drive • Analisi creditizia • Dossier banca')

tab1, tab2, tab3 = st.tabs(['Dashboard GOLD','Document AI','Analytics Engine'])
with tab1:
    st.subheader('Centro di controllo FinancePlus')
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Workflow','Gmail → IA → Drive')
    c2.metric('CRM','Airtable relazionale')
    c3.metric('Credito','KPI + CR + CC')
    c4.metric('Guardrail','No dati inventati')
    st.info('Versione GOLD: separa storage, database, servizi e calcoli deterministici. Le integrazioni esterne richiedono credenziali/connector configurati nei Secrets.')
with tab2:
    st.subheader('Classificazione e naming')
    text=st.text_area('Incolla testo estratto dal documento', height=220)
    company=st.text_input('Azienda / soggetto')
    year=st.number_input('Anno documento (0 = non disponibile)', min_value=0, max_value=2100, value=0)
    if st.button('Analizza documento'):
        r=classify_text(text); r.company_name=company; r.document_year=int(year) or None
        st.json({'categoria':r.category,'confidenza':r.confidence,'nome_proposto':suggested_name(r)})
with tab3:
    st.subheader('Analisi finanziaria prudenziale')
    names=['revenue','ebitda','ebit','financial_debt','cash','equity','current_assets','current_liabilities','cfads','debt_service']
    labels=['Ricavi','EBITDA','EBIT','Debiti finanziari','Cassa','Patrimonio netto','Attivo corrente','Passivo corrente','CFADS','Servizio debito']
    values={}
    for n,l in zip(names,labels):
        raw=st.text_input(l, key=n, placeholder='Lascia vuoto se non verificato')
        try: values[n]=float(raw.replace('.','').replace(',','.')) if raw.strip() else None
        except ValueError: values[n]=None
    if st.button('Calcola KPI e rating'):
        result=analyze(FinancialInputs(**values))
        st.json(result.__dict__)
        if result.score is None: st.warning('Rating bloccato: dati insufficienti.')
