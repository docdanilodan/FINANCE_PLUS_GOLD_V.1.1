# FINANCEPLUS DESKTOP V1.0

Versione desktop standalone del progetto FinancePlus, mantenuta nello stesso repository della web app Streamlit.

## Avvio Windows

1. Scarica la cartella `desktop` o il pacchetto ZIP distribuito con la release.
2. Esegui `INSTALLA_E_AVVIA_WINDOWS.bat`.
3. L'installer crea `.venv`, installa le dipendenze e avvia `FINANCEPLUS_DESKTOP_V1_0.py`.
4. I dati locali vengono salvati nella cartella FinancePlus dell'utente Windows tramite SQLite e archivio locale.

## EXE

Esegui `CREA_EXE_WINDOWS.bat` per generare:

`dist\FINANCEPLUS_DESKTOP_V1_0.exe`

La compilazione EXE deve essere eseguita su Windows e viene effettuata con PyInstaller.

## Funzioni

- Dashboard
- Clienti 360
- Pratiche e workflow
- Archivio documentale con SHA-256
- Gmail / Aruba IMAP
- Document AI
- Analytics + Data Quality Gate
- Centrale Rischi
- Conti Correnti
- Business Plan 5 anni
- Dossier / Fascicolo / Riepilogo PDF
- Mandati e compensi
- Backup ZIP

## Sicurezza

Nessuna password o token deve essere commesso nel repository. Gmail, Aruba, Airtable e Drive vanno configurati tramite Secrets o credenziali richieste a runtime secondo la modalita di esecuzione.

## Web app

La versione Streamlit usa `streamlit_app.py` ed e allineata alle macro-funzioni Desktop tramite `streamlit_desktop_aligned.py`.
