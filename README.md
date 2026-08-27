# FINANCE_PLUS_GOLD 2.0

FinancePlus GOLD è il centro operativo consolidato per **CRM, Document AI, email/documenti, Centrale Rischi, analisi conti correnti, merito creditizio, Business Plan e dossier banca**.

## Pipeline

`Gmail / Upload → Document AI → Drive → Airtable → Analytics Engine → CR + CC → Rating → Business Plan → Dossier`

## Moduli GOLD 2.0

- `app.py`: dashboard Streamlit a 7 aree.
- `document_ai.py`: classificazione e naming documentale.
- `analytics_engine.py`: KPI, Data Quality Gate, score e rating AAA–D.
- `services/airtable_adapter.py`: adapter REST verso la base reale FinancePlus AI.
- `modules/credit_risk.py`: analisi Centrale Rischi multi-mese.
- `modules/bank_account.py`: cash-flow da movimenti bancari CSV.
- `modules/business_plan.py`: proiezione economica quinquennale.
- `modules/dossier.py`: generatore dossier bancario strutturato.

## Airtable reale verificato

Base `FinancePlus AI`: Clienti, Pratiche, Documenti, Email, Analisi Creditizie. Sono presenti linked records Cliente/Pratica, completezza dossier, alert, CR aggiornata, rating, KPI e anagrafica camerale.

## Guardrail

FinancePlus non deve inventare PFN, DSCR, score, rating, probabilità di delibera o importi sostenibili. I dati mancanti restano `N/D` o `INCOMPLETO`; l'IA interpreta, mentre i KPI sono calcolati deterministicamente.

## Secrets

Non inserire token nel repository. Configurare in Streamlit Secrets / environment:

```toml
AIRTABLE_TOKEN="..."
AIRTABLE_BASE_ID="appoNJtS64JIcZUhT"
```

Le integrazioni Gmail/Drive in ChatGPT restano connettori autorizzati; per esecuzione autonoma fuori ChatGPT serviranno credenziali OAuth dedicate.

## Avvio

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

**Edizione GOLD 2.0 — 27/08/2026**
