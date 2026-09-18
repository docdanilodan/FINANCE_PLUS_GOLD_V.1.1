# FINANCE_PLUS_UNICO V_1.1 — Architettura

## Obiettivo

Una sola interfaccia Streamlit e un solo flusso operativo, mantenendo separati codice, dati, documenti e credenziali.

```text
Utente
  ↓
streamlit_app.py
  ↓
streamlit_desktop_aligned.py
  ├─ Dashboard / Brief operativo
  ├─ Cliente 360 + Pratiche
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

## Data layer — fase read-shadow

```text
                ┌─────────────────────────┐
                │  Neon PostgreSQL        │
                │  core cloud preferito   │
                └────────────┬────────────┘
                             │
                  attivo solo se clients
                  contiene dati operativi
                             │
                             ▼
                HybridDataProvider
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
       Neon read source              Airtable fallback
 Cliente/Pratiche/Documenti/         compatibilita web,
 Analisi                              email e write legacy
              │
              ▼
          Cliente 360

Desktop Edition -> SQLite locale/offline
```

### Regola di cutover

- se Neon è configurato **e** la tabella `clients` contiene almeno un record, Cliente 360, Pratiche, Documenti e Analisi leggono da Neon;
- se Neon è configurato ma vuoto/non raggiungibile, la web app continua a leggere da Airtable;
- email, eventi e proposte restano sul layer Airtable nella fase read-shadow;
- i record letti da Neon sono in sola lettura: nessuna scrittura diretta o write-through viene eseguita prima della migrazione controllata;
- SQLite resta il backend locale/offline della Desktop Edition.

Airtable non è più definito come secondo core database: durante questa fase è un compatibility layer. Google Drive conserva i file; Gmail/Aruba alimentano la pipeline documentale; GitHub conserva codice e CI.

## Pipeline documentale

```text
Gmail / Upload
  → lettura contenuto
  → Document Intelligence
  → naming
  → SHA-256
  → matching Cliente / Pratica
  → storage
  → metadata operativi
  → Data Quality Gate
  → alert / dossier
```

La pipeline Gmail continua temporaneamente a registrare i metadati su Airtable fino alla fase write-through Neon.

## Pipeline creditizia

```text
Bilancio + CR + Conti correnti
  → Data Quality Gate
  → KPI deterministici
  → score interno / rating simulato solo se supportati
  → stress test
  → Funding Intelligence
  → Dossier Banca / Fascicolo Cliente
```

Score interno, simulazioni MCC e criteri pubblici degli operatori restano distinti.

## Sicurezza

Le credenziali sono caricate dai Secrets del deployment. Nessun token, connection string Neon, password o OAuth deve essere scritto nei file del repository.

## Compatibilità e rollback

`app.py` e `FinancePlus_Airtable/streamlit_app.py` restano compatibility entrypoint verso la web master.

Il read-shadow è reversibile: rimuovendo `NEON_DATABASE_URL` / `DATABASE_URL` oppure con core Neon vuoto, la web app torna automaticamente al fallback Airtable senza cancellare dati.
