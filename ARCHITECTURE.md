# FINANCE_PLUS_UNICO V_1.0 — Architettura

## Obiettivo

Una sola interfaccia Streamlit e un solo flusso operativo, mantenendo separati codice, dati, documenti e credenziali.

```text
Utente
  ↓
streamlit_app.py
  ↓
master_app.py
  ├─ Dashboard / Brief operativo
  ├─ Clienti + Pratiche
  ├─ Archivio Documenti
  ├─ Document AI
  ├─ Gmail & Drive
  ├─ Analytics Engine
  ├─ Centrale Rischi
  ├─ Conti Correnti
  ├─ Business Plan
  ├─ Dossier Banca
  └─ Mandati
```

## Data layer

```text
Airtable FinancePlus AI
  Clienti
    → Pratiche
    → Documenti
    → Email
    → Analisi Creditizie
```

Airtable è il CRM strutturato. Google Drive conserva i file. Gmail alimenta la pipeline documentale. GitHub conserva esclusivamente il codice.

## Pipeline documentale

```text
Gmail / Upload
  → lettura contenuto
  → Document AI
  → naming
  → SHA-256
  → matching Cliente / Pratica
  → Google Drive
  → Airtable
  → alert / dossier
```

## Pipeline creditizia

```text
Bilancio + CR + Conti correnti
  → Data Quality Gate
  → KPI deterministici
  → score / rating solo se supportati
  → Business Plan
  → Dossier Banca / Fascicolo Cliente
```

## Sicurezza

Le credenziali sono caricate dai Secrets del deployment. Nessun token Airtable o Google deve essere scritto nei file del repository.

## Compatibilità

`app.py` e `FinancePlus_Airtable/streamlit_app.py` sono compatibility entrypoint: entrambi aprono `master_app.py`. La UI operativa è quindi unica anche se un vecchio deployment conserva un percorso storico.
