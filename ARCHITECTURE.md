# FinancePlus GOLD — Architettura target

## Layer
1. **UI**: Streamlit, dashboard, filtri, anteprime.
2. **Services**: mail, documenti, IA, scoring, report, CData.
3. **Database**: Airtable operativo; PostgreSQL target robusto.
4. **Storage**: Drive / filesystem controllato / S3-compatible.
5. **Audit**: hash, source ID, stato verifica, log operazioni.

## Data model minimo
- Clienti: denominazione, PIVA/CF, PEC, Drive, rating corrente.
- Pratiche: cliente, istituto, importo, stato, priorità, prossima azione.
- Email: message_id, thread_id, mittente, oggetto, data, pratica.
- Documenti: source_id, sha256, categoria, periodo, URL, stato verifica.
- Analisi Creditizie: KPI, score, rating, criticità, versione e fonte.

## Regola critica
Nessuna pagina UI deve contenere direttamente credenziali o logica di accesso a Gmail, Drive, Airtable, CData o OpenAI. Le integrazioni devono essere incapsulate nei servizi.
