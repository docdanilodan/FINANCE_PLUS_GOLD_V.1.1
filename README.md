# FINANCE_PLUS_UNICO V_1.1

Repository unico per la versione web Streamlit e per la Desktop Edition standalone di FinancePlus.

## 1. Streamlit Cloud - app master

Entry point ufficiale:

```text
streamlit_app.py
```

`streamlit_app.py` applica il branding **FINANCE_PLUS_UNICO V_1.1** e avvia `master_app.py`, che resta il cuore della web app. I precedenti `app.py` e `FinancePlus_Airtable/streamlit_app.py` sono mantenuti solo come compatibility entrypoint.

### Funzioni web integrate

1. Dashboard operativa con Clienti, Pratiche, Documenti, Email, Analisi e alert dossier.
2. Clienti Airtable con ricerca, anagrafica camerale, modifica dati e linked records.
3. Pratiche con banca/intermediario, importo, priorita, responsabile, prossima azione, scadenza e documenti mancanti.
4. Archivio documentale con filtri, origine, stato verifica, SHA-256 e link Drive.
5. Report Cliente PDF e Fascicolo Cliente PDF.
6. Document AI content-first per classificazione e naming.
7. Gmail / Google Drive con deduplica e matching Cliente/Pratica.
8. Aruba Mail multi-account tramite IMAP e Secrets.
9. Analytics Engine con Data Quality Gate, KPI, score, rating AAA-D e semaforo.
10. Centrale Rischi multi-mese.
11. Conti correnti.
12. Business Plan a 5 anni.
13. Dossier Banca PDF + Markdown.
14. Mandati e simulazione compensi.

Pipeline web:

```text
Gmail / Aruba / Upload
  -> Document AI
  -> Deduplica SHA-256
  -> Google Drive
  -> Airtable CRM
  -> Analytics + Centrale Rischi + Conti Correnti
  -> Business Plan
  -> Dossier / Fascicolo Cliente PDF
```

## 2. Desktop Edition standalone

La cartella:

```text
desktop/
```

contiene la versione desktop verificata **FINANCE_PLUS_UNICO DESKTOP V1.0**, local-first, con SQLite e archivio locale.

File principali:

```text
desktop/FINANCE_PLUS_UNICO_DESKTOP.py
desktop/INSTALLA_WINDOWS.bat
desktop/AVVIA_SENZA_INSTALLARE_WINDOWS.bat
desktop/CREA_EXE_WINDOWS.bat
desktop/requirements.txt
desktop/README_INSTALLAZIONE.txt
```

La Desktop Edition comprende Dashboard, CRM clienti, Pratiche, Archivio documentale, SHA-256, Document AI locale, Analytics, Centrale Rischi CSV, Conti Correnti CSV, Business Plan, Dossier Banca, Mandati e Fascicolo Cliente PDF.

### Installazione Windows

1. Scaricare o clonare il repository.
2. Aprire la cartella `desktop`.
3. Eseguire `INSTALLA_WINDOWS.bat`.
4. L'installer crea un ambiente Python isolato e un collegamento `FINANCE_PLUS_UNICO` sul Desktop.

Per creare l'eseguibile Windows:

```text
CREA_EXE_WINDOWS.bat
```

Il vero `.exe` deve essere compilato su Windows con PyInstaller; non viene pubblicato un eseguibile non testato cross-platform.

## 3. Secrets e sicurezza

Le credenziali non devono essere pubblicate nel repository.

Configurare in Streamlit Cloud esclusivamente i Secrets necessari, ad esempio:

```toml
AIRTABLE_TOKEN = "..."
AIRTABLE_BASE_ID = "appoNJtS64JIcZUhT"
GOOGLE_OAUTH_TOKEN_JSON = "..."
GOOGLE_DRIVE_FOLDER_ID = "..."

ARUBA_D_DANGELO_EMAIL = "d.dangelo@financeplus.tech"
ARUBA_D_DANGELO_PASSWORD = "..."
ARUBA_PRATICHE_EMAIL = "pratiche@financeplus.tech"
ARUBA_PRATICHE_PASSWORD = "..."
```

Token, password e API key non devono essere inseriti nel codice.

## 4. Principio di controllo FinancePlus

FinancePlus non inventa dati finanziari mancanti. Se la fonte non permette di calcolare correttamente PFN, DSCR, rating o altri indicatori, il valore resta `N/D` / `INCOMPLETO` ed e segnalato dal Data Quality Gate.

## 5. Architettura

- GitHub: codice e versionamento.
- Streamlit: web app operativa.
- Airtable: CRM e dati strutturati.
- Google Drive: storage documentale.
- Gmail / Aruba: sorgenti email e allegati.
- Desktop Edition: uso locale con SQLite e archivio locale.
- Secrets: credenziali e token protetti.
