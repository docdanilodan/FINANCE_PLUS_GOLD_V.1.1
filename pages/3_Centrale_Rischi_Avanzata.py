from __future__ import annotations
import json, tempfile
from pathlib import Path
import pandas as pd
import streamlit as st
from financeplus_cr_engine import parse_file, analyze, generate_pdf

st.set_page_config(page_title='FinancePlus - Centrale Rischi Avanzata', page_icon='🏦', layout='wide')
st.title('Centrale Rischi - Motore CR_2026_2_CORRETTO')
st.caption('Modulo additivo di FINANCE_PLUS_UNICO V_1.1. La modalita CR rapida esistente resta disponibile.')
upload=st.file_uploader('Carica Centrale Rischi Banca d’Italia',type=['pdf','txt','csv','xlsx','xls','json'])
if upload:
    suffix=Path(upload.name).suffix
    with tempfile.TemporaryDirectory() as td:
        src=Path(td)/('input'+suffix); src.write_bytes(upload.getvalue())
        try:
            parsed=parse_file(src); result=analyze(parsed)
            st.session_state['last_cr_advanced']=result.to_dict()
            a,b,c,d=st.columns(4); a.metric('Score',f'{result.score}/100'); b.metric('Rating',result.rating); c.metric('PD stimata',f'{result.pd:.2f}%'); d.metric('Audit','OK' if result.audit.valid else 'BLOCCATO')
            st.write(f'**Soggetto:** {result.subject}'); st.write(f'**Codice fiscale/P.IVA:** {result.tax_code or "N/D"}')
            if result.monthly: st.dataframe(pd.DataFrame(result.monthly),use_container_width=True,hide_index=True)
            if result.anomalies: st.warning(' | '.join(result.anomalies))
            if result.audit.warnings:
                with st.expander('Avvisi audit'): st.write('\n'.join('- '+x for x in result.audit.warnings))
            if result.audit.errors:
                st.error('Controllo di congruita non superato. Il PDF professionale resta bloccato finche gli errori non sono risolti.')
                with st.expander('Errori audit'): st.write('\n'.join('- '+x for x in result.audit.errors))
            else:
                out=Path(td)/'FinancePlus_CR_Avanzata.pdf'; generate_pdf(result,out)
                st.download_button('Scarica report CR professionale - 45 pagine',data=out.read_bytes(),file_name='FinancePlus_CR_Avanzata.pdf',mime='application/pdf',type='primary')
            st.download_button('Scarica audit JSON',data=json.dumps(result.to_dict(),ensure_ascii=False,indent=2),file_name='FinancePlus_CR_Audit.json',mime='application/json')
        except Exception as exc: st.error(f'Analisi CR non completata: {exc}')
