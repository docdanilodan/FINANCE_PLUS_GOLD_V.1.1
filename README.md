# FINANCE_PLUS_GOLD 3.0

FinancePlus GOLD integra **CRM Airtable, Gmail, Google Drive, Document AI, Centrale Rischi, conti correnti, Analytics Engine, Business Plan e dossier bancario PDF**.

## Pipeline GOLD 3.0

`Gmail → allegati → deduplica SHA-256 → Document AI → Drive → Airtable → verifica → Analytics → CR + CC → Rating → Business Plan → Dossier PDF`

## Componenti

- `app.py` — dashboard Streamlit GOLD.
- `document_ai.py` — classificazione/naming con regole FinancePlus.
- `analytics_engine.py` — KPI, Data Quality Gate, score/rating.
- `services/airtable_adapter.py` — CRUD/upsert Airtable.
- `services/google_auth.py` — OAuth Google da Secret.
- `services/gmail_drive_pipeline.py` — ingestion Gmail→Drive→Airtable.
- `modules/credit_risk.py` — Centrale Rischi.
- `modules/bank_account.py` — cash-flow conti correnti.
- `modules/business_plan.py` — proiezione 5 anni.
- `modules/dossier.py` — dossier Markdown.
- `modules/pdf_dossier.py` — dossier PDF professionale.

## Stato Airtable

La struttura FinancePlus è relazionale: `Clienti → Pratiche → Documenti / Email / Analisi Creditizie`. L'anagrafica camerale può includere P.IVA, CF, PEC, REA, sede, CAP, ATECO, capitale sociale, amministratore e stato verifica.

## Sicurezza e Data Quality

- Nessun token/API key nel repository.
- Deduplica documenti tramite SHA-256.
- Documenti provenienti dalla pipeline entrano inizialmente come `Da verificare`.
- Il nome originario non è prova sufficiente della tipologia documentale.
- Rating, PFN, DSCR, probabilità delibera e capacità finanziabile non vengono inventati.

## Secrets richiesti per esecuzione autonoma

```toml
AIRTABLE_TOKEN="..."
AIRTABLE_BASE_ID="appoNJtS64JIcZUhT"
GOOGLE_OAUTH_TOKEN_JSON='{"token":"...","refresh_token":"...","client_id":"...","client_secret":"...","token_uri":"https://oauth2.googleapis.com/token"}'
GOOGLE_DRIVE_FOLDER_ID="..."
```

Le connessioni Gmail/Drive già autorizzate dentro ChatGPT non trasferiscono automaticamente le credenziali a Streamlit: il deploy autonomo richiede OAuth Google dedicato.

## Avvio

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

**Edizione GOLD 3.0 — 27/08/2026**
