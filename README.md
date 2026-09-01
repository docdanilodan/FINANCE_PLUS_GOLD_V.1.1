# FINANCE_PLUS_UNICO V_1.0

Questa repository espone **una sola app Streamlit master**, costruita consolidando le migliori funzioni delle precedenti varianti FinancePlus GOLD / NEUTRO / PLATINUM / DIAMOND / Airtable.

## Entry point unico

Per Streamlit Cloud usare:

```text
streamlit_app.py
```

Anche i precedenti `app.py` e `FinancePlus_Airtable/streamlit_app.py` sono mantenuti esclusivamente come **compatibility entrypoint** e aprono la stessa app master.

## Funzioni integrate

1. **Dashboard operativa** con Clienti, Pratiche, Documenti, Email, Analisi e alert dossier.
2. **Clienti Airtable** con ricerca, anagrafica camerale, modifica dati e linked records.
3. **Pratiche** con creazione dal cliente, banca/intermediario, importo, priorità, responsabile, prossima azione, scadenza e documenti mancanti.
4. **Archivio Smart** con acquisizione da PC/iPhone/Android, fotocamera, OCR locale, anteprima obbligatoria, classificazione, filtri, stato verifica, SHA-256 e link Drive.
5. **Report Cliente PDF** con documenti e controllo pratiche.
6. **Fascicolo Cliente PDF** con anagrafica, documenti, pratiche, email e analisi creditizie.
7. **Document AI** content-first per classificazione e naming di visure, bilanci, ricevute deposito, bozze, analitici, prospetti, CR, estratti conto, fatture, contratti, DURC, CV, offerte, preventivi e presentazioni.
8. **Gmail → Drive → Airtable** con deduplica `Gmail Message ID` + `SHA-256` e matching Cliente/Pratica.
9. **Multi-profilo Google**: oltre a `GOOGLE_OAUTH_TOKEN_JSON`, si possono aggiungere Secrets del tipo `GOOGLE_OAUTH_TOKEN_JSON_<NOME>` e scegliere la casella dalla UI.
10. **FinancePlus Analytics Engine** con Data Quality Gate, EBITDA margin, PFN, PFN/EBITDA, Debt/Equity, Current Ratio, DSCR, score, rating AAA–D e semaforo.
11. **Centrale Rischi** multi-mese con utilizzo affidamenti, scaduti/sconfinamenti e sofferenze.
12. **Conti correnti** con entrate, uscite, cash-flow netto, media mensile e mesi negativi.
13. **Business Plan** a 5 anni.
14. **Dossier Banca** PDF + Markdown.
15. **Mandati** con simulatore parametrico del compenso e storico CSV della sessione.

## Pipeline unica

```text
Gmail / Upload / Fotocamera cellulare
  → Archivio Smart (OCR locale + verifica umana)
  → Document AI
  → Deduplica SHA-256
  → Google Drive
  → Airtable CRM
  → Analytics + Centrale Rischi + Conti Correnti
  → Business Plan
  → Dossier Banca / Fascicolo Cliente PDF
```

## Principio di controllo

FinancePlus non inventa dati finanziari mancanti. Se la fonte non consente di calcolare correttamente PFN, DSCR, rating o altri indicatori, il dato resta `N/D` / `INCOMPLETO` e viene segnalato dal Data Quality Gate.

## Secrets Streamlit

Configurare esclusivamente nei Secrets del deployment:

```toml
AIRTABLE_TOKEN = "..."
AIRTABLE_BASE_ID = "appoNJtS64JIcZUhT"
GOOGLE_OAUTH_TOKEN_JSON = "..."
GOOGLE_DRIVE_FOLDER_ID = "..."

# Profili Google aggiuntivi opzionali
GOOGLE_OAUTH_TOKEN_JSON_STUDIO = "..."
GOOGLE_OAUTH_TOKEN_JSON_PRATICHE = "..."

# OCR locale (nessun invio cloud automatico)
FINANCEPLUS_OCR_LANGUAGES = "ita+eng"
FINANCEPLUS_OCR_MAX_PAGES = "30"
FINANCEPLUS_SMART_ARCHIVE_CLOUD_EXTRACTOR = "false"
```

I token non devono essere pubblicati nel repository.

## Architettura

- **GitHub**: codice e versionamento.
- **Airtable**: CRM e dati strutturati.
- **Google Drive**: storage documentale.
- **Gmail**: sorgente email/allegati.
- **Streamlit**: interfaccia operativa.
- **Secrets**: credenziali e token.

## File principali

```text
streamlit_app.py              # entrypoint unico
master_app.py                 # UI master
analytics_engine.py           # KPI, score e Data Quality Gate
document_ai.py                # classificazione e naming
modules/                      # CR, CC, BP, dossier, PDF, mandati
services/                     # Airtable, Gmail/Drive, matching cliente/pratica
services/smart_archive.py     # analisi e commit coordinato Drive/Airtable
modules/smart_archive_ui.py   # interfaccia mobile/desktop Archivio Smart
FinancePlus_Airtable/         # generatori PDF e compatibilità legacy
```

## Archivio Smart

Dal menu **🗂️ Archivio Smart**:

1. scegliere il profilo Google/Drive;
2. caricare uno o più documenti oppure usare la fotocamera del cellulare;
3. premere **Analizza e riconosci**;
4. verificare categoria, cliente, pratica, esercizio e nome definitivo;
5. confermare il salvataggio su Drive e l'indicizzazione in Airtable.

I PDF nativi, i PDF scansionati, le immagini, i file TXT/CSV/XML/JSON, Word,
Excel e PowerPoint vengono letti localmente. Le immagini HEIC dell'iPhone sono
supportate. I duplicati sono bloccati tramite SHA-256 prima del caricamento e
nuovamente al momento del salvataggio.

La struttura generata per i documenti riconosciuti è:

```text
FINANCE_V.1.1_ARCHIVIO/
  CLIENTI/<CLIENTE>/<ANNO>/<PRATICA>/<CATEGORIA>/
```

I documenti senza cliente certo vengono collocati in
`DA_VERIFICARE/<ANNO>/<CATEGORIA>`. Se il salvataggio Airtable fallisce, il file
Drive appena creato viene rimosso automaticamente per evitare documenti orfani.

Su Streamlit Cloud il file `packages.txt` installa Tesseract e la lingua
italiana. Per impostazione predefinita Archivio Smart usa soltanto OCR locale:
il livello cloud opzionale resta disattivato finché
`FINANCEPLUS_SMART_ARCHIVE_CLOUD_EXTRACTOR` non viene impostato esplicitamente a
`true`.

## Deploy

Main file path consigliato:

```text
streamlit_app.py
```

Dopo aver configurato i Secrets, il deploy usa direttamente la base Airtable e, se autorizzato, i profili Gmail/Drive selezionabili dalla schermata dedicata.
