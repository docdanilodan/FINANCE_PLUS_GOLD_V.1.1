FINANCE_PLUS_UNICO DESKTOP V1.1
================================

INSTALLAZIONE CONSIGLIATA (WINDOWS 10/11)
1. Estrarre tutto lo ZIP in una cartella.
2. Fare doppio clic su INSTALLA_WINDOWS.bat.
3. L'installer verifica Python, crea un ambiente isolato, installa le dipendenze e crea un collegamento Desktop.
4. Aprire FINANCE_PLUS_UNICO dal Desktop.

DOVE SALVA I DATI
- Database SQLite e configurazione: %LOCALAPPDATA%\FinancePlusUnico
- Archivio documenti: %LOCALAPPDATA%\FinancePlusUnico\archive
- PDF/Markdown generati: %LOCALAPPDATA%\FinancePlusUnico\output

FUNZIONI LOCALI ATTIVE SENZA CLOUD
- Dashboard e CRM clienti
- Pratiche
- Archivio documentale e SHA-256
- Document AI locale per PDF testuali/TXT/CSV/MD
- Analytics, Data Quality Gate, KPI, rating e semaforo
- Centrale Rischi CSV
- Conti Correnti CSV
- Business Plan a 5 anni
- Dossier Banca PDF + Markdown
- Mandati e storico CSV
- Report e Fascicolo Cliente PDF

INTEGRAZIONI FACOLTATIVE
Aprire Configurazione nel programma e inserire, se disponibili:
- Airtable Token + Base ID
- Google OAuth Token JSON + Drive Folder ID
- OpenAI API Key
- Adobe PDF Services Client ID + Secret

CREAZIONE .EXE
Su un PC Windows, eseguire CREA_EXE_WINDOWS.bat. Il file FINANCE_PLUS_UNICO_DESKTOP_V1_1.exe verrà creato in dist\.
PyInstaller non permette di creare correttamente un EXE Windows da Linux/macOS: per questo lo script di build è incluso nel pacchetto.

SICUREZZA
Le credenziali non sono incluse nel programma e non sono pubblicate nel codice. Sono salvate localmente nel file config.json dell'utente.
