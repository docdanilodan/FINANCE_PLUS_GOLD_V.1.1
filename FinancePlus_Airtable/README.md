# FinancePlus Airtable

App Streamlit dedicata alla consultazione della base Airtable **FinancePlus AI**.

## Funzioni

- Dashboard con conteggi Clienti, Pratiche, Documenti, Email e alert visure datate.
- Anagrafica camerale Clienti con ricerca, filtri e scheda completa.
- Consultazione Pratiche con stato, priorita, istituto, importi e prossime azioni.
- Consultazione Documenti con classificazione, naming IA, Drive e stato verifica.
- Consultazione Email con priorita, sintesi e azioni richieste.
- Consultazione Analisi Creditizie con KPI, Score, Rating, DSCR e PFN/EBITDA.
- Cache breve e pulsante di aggiornamento dati.
- Nessun token Airtable salvato nel repository.

## Base Airtable

Default base ID: `appoNJtS64JIcZUhT`

Tabelle utilizzate:

- `Clienti`
- `Pratiche`
- `Documenti`
- `Email`
- `Analisi Creditizie`

## Deploy su Streamlit Cloud

Usare come entrypoint:

`FinancePlus_Airtable/streamlit_app.py`

Nei **Secrets** della app inserire:

```toml
AIRTABLE_TOKEN = "pat_xxxxxxxxxxxxxxxxx"
AIRTABLE_BASE_ID = "appoNJtS64JIcZUhT"
```

Il PAT Airtable deve avere accesso alla base FinancePlus AI. Le credenziali non devono essere committate in GitHub.

## Architettura

`Streamlit UI -> Airtable REST API -> FinancePlus AI base`

L'app e intenzionalmente separata dal motore analitico FINANCE_PLUS_GOLD: questa versione e un front-end CRM/Airtable focalizzato su consultazione operativa e dossier cliente.
