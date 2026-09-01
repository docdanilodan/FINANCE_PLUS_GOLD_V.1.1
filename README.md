# FINANCE_PLUS_UNICO V_1.1

Repository unico per la **web app Streamlit** e la **Desktop Edition standalone** di FinancePlus.

## 1. Streamlit Cloud - app ufficiale

Entry point ufficiale:

```text
streamlit_app.py
```

Il flusso attivo e ora:

```text
streamlit_app.py
  -> streamlit_desktop_aligned.py
  -> servizi/moduli FinancePlus
```

`streamlit_desktop_aligned.py` e la web master **FINANCE_PLUS_UNICO V_1.1 Web/Desktop aligned**. `master_app.py` resta nel repository come base precedente/fallback e non viene cancellato.

Anche gli entrypoint di compatibilita:

```text
app.py
FinancePlus_Airtable/streamlit_app.py
```

aprono la stessa applicazione V_1.1.

### Macro-funzioni web

1. Dashboard operativa.
2. Clienti 360 Airtable con ricerca, anagrafica e linked records.
3. Pratiche e workflow con stato, priorita, responsabile, scadenze, documenti mancanti e alert.
4. Archivio Documenti con filtri, origine, SHA-256, stato verifica e link Drive.
5. Document AI content-first, classificazione e naming automatico.
6. Email e Google Drive, con pipeline Gmail -> Drive -> Airtable.
7. Aruba Mail multi-account tramite IMAP e Secrets.
8. Analisi Creditizie con Data Quality Gate, KPI, score e rating AAA-D.
9. Centrale Rischi multi-mese.
10. Conti Correnti e cash-flow.
11. Business Plan a 5 anni.
12. Report PDF: Report Cliente, Fascicolo Cliente e Dossier Banca.
13. Mandati e simulazione compensi.
14. Impostazioni con stato connessioni e Secrets richiesti.

### Grafica V_1.1

La web app usa un workspace coerente con la Desktop Edition: sidebar blu notte, accenti rame, card bianche, navigazione per macro-funzioni e cruscotti operativi.

### Pipeline web

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

La cartella ufficiale e:

```text
desktop/
```

Distribuzione raccomandata:

```text
desktop/FINANCEPLUS_DESKTOP_V1_0.py
desktop/INSTALLA_E_AVVIA_WINDOWS.bat
desktop/AVVIA_FINANCEPLUS.bat
desktop/CREA_EXE_WINDOWS.bat
desktop/requirements.txt
desktop/README.md
desktop/ESEMPI/
```

La Desktop Edition usa **SQLite e archivio locale**, quindi puo funzionare anche senza Airtable o Drive. Comprende Dashboard, Clienti 360, Pratiche, Documenti, Document AI, Email/IMAP, Analytics, CR, Conti Correnti, Business Plan, Report PDF, Mandati e Backup.

Nel repository restano anche alcuni file Desktop precedenti per compatibilita; non sono stati cancellati per non rompere flussi gia esistenti.

### Installazione Windows

1. Scaricare o clonare il repository.
2. Aprire `desktop/`.
3. Eseguire `INSTALLA_E_AVVIA_WINDOWS.bat`.
4. L'installer crea un ambiente Python isolato, installa le librerie e avvia il programma.

Per generare un vero eseguibile Windows:

```text
CREA_EXE_WINDOWS.bat
```

Output previsto:

```text
dist\FINANCEPLUS_DESKTOP_V1_0.exe
```

L'EXE va compilato e collaudato su Windows con PyInstaller.

## 3. Streamlit Cloud

Main file path:

```text
streamlit_app.py
```

Se un deployment Streamlit Cloud e gia collegato a questo repository, branch `main`, e a `streamlit_app.py`, i push su `main` vengono normalmente recepiti dal deployment. Se il deploy non esiste ancora, creare l'app Streamlit scegliendo questo repository e questo Main file path.

## 4. Secrets e sicurezza

Le credenziali non devono essere pubblicate nel repository.

Esempio Streamlit Secrets:

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

Token, password e API key non devono essere inseriti nel codice GitHub.

## 5. Principio FinancePlus

FinancePlus non inventa dati finanziari mancanti. Se la fonte non consente di calcolare correttamente PFN, DSCR, rating o altri indicatori, il valore resta `N/D` / `INCOMPLETO` ed e gestito dal **Data Quality Gate**.

## 6. Architettura finale

- **GitHub**: codice, versionamento, CI e automazioni.
- **Streamlit**: web app operativa.
- **Airtable**: CRM e dati strutturati.
- **Google Drive**: storage documentale.
- **Gmail / Aruba**: sorgenti email e allegati.
- **Desktop Edition**: uso locale con SQLite e archivio locale.
- **Secrets**: credenziali e token protetti.
