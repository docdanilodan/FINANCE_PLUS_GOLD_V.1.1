# FINANCE_PLUS_GOLD

**FinancePlus GOLD** è la versione consolidata del progetto FinancePlus 360 AI: un centro operativo per documenti, email, CRM, analisi del merito creditizio e dossier bancari.

## Architettura GOLD

`Gmail / Upload → Document AI → Google Drive → Airtable → Analytics Engine → Brief / Rating / Dossier`

Principi:
- storage e database separati;
- relazioni Cliente → Pratica → Documenti / Email / Analisi;
- SHA-256 e identificativi persistenti per deduplica;
- calcoli finanziari deterministici;
- IA usata per estrarre, classificare, sintetizzare e commentare;
- **mai inventare PFN, DSCR, rating o importo finanziabile** quando i dati non sono sufficienti;
- audit e stato `Da verificare / Verificato` per i dati decisivi.

## Moduli inclusi

- `app.py` — dashboard Streamlit GOLD.
- `document_ai.py` — classificazione e naming documentale.
- `analytics_engine.py` — KPI, data quality, scoring e guardrail.
- `streamlit_app.py` — entrypoint Streamlit Cloud.

## Naming Document AI

Supporta prioritariamente:
- Visura Camerale
- Bilancio d'esercizio
- Ricevuta deposito Bilancio
- Centrale Rischi Banca d'Italia
- Estratto conto
- Fattura
- Contratto di finanziamento
- DURC
- Preventivo / Offerta
- Curriculum Vitae

Le regole specifiche precedono la regola generica `SOGGETTO_TIPO DOCUMENTO_ANNO.estensione`.

## FinancePlus Analytics Engine

KPI previsti: EBITDA margin, PFN, PFN/EBITDA, Debt/Equity, Current Ratio, DSCR e successivamente CR 12/36 mesi, cash-flow, stress test e capacità finanziabile.

Il motore applica un **Data Quality Gate**: con dati insufficienti restituisce `INCOMPLETO` e non forza un rating.

## Integrazioni target

- Gmail: email, thread, allegati, brief e bozze.
- Google Drive: archivio originale e cartelle cliente/pratica.
- Airtable: Clienti, Pratiche, Documenti, Email, Analisi Creditizie.
- CData Connect AI: fonti SQL e metadati GitHub.
- OpenAI Platform / ChatGPT: Document AI, sintesi e commento.
- Adobe Acrobat: OCR e PDF difficili quando necessario.

## Avvio

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Stato

Edizione **GOLD 1.0 — 27/08/2026**. Base consolidata pronta per evolvere verso servizi Gmail/Drive/Airtable reali, report PDF e moduli CR/conti correnti/business plan.
