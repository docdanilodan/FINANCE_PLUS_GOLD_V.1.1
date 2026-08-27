# FinancePlus Airtable

App Streamlit dedicata alla consultazione e gestione della base Airtable **FinancePlus AI**.

## Versione 1.3

La sezione **👥 Clienti** e operativa in lettura e scrittura e include ora il riepilogo documentale PDF per ogni cliente.

### Funzioni Clienti

- ricerca per ragione sociale, Partita IVA, Codice Fiscale, PEC, REA, Comune, Provincia, ATECO e amministratore;
- filtri per Provincia, Stato attivita e Stato verifica anagrafica;
- apertura della scheda cliente senza uscire da Streamlit;
- anagrafica camerale completa con P.IVA, CF, PEC, REA, sede, CAP, forma giuridica, ATECO, attivita prevalente, capitale sociale e amministratore;
- alert automatico se l'ultima visura ha oltre 180 giorni;
- indicatori rapidi su rating, numero pratiche e documenti;
- dossier FinancePlus con CR aggiornata, ultimo bilancio, ultima visura e stato verifica;
- tab **Pratiche** collegate;
- tab **Documenti** collegati, con link diretto a Google Drive quando disponibile;
- pulsante **Vedi riepilogo documenti** per mostrare la tabella sintetica di tutti i documenti del cliente;
- pulsante **Scarica riepilogo PDF** con report A4 orizzontale multipagina, dati cliente, conteggio documenti e link Drive cliccabili quando presenti;
- tab **Email** collegate, ordinate dalla piu recente;
- tab **Analisi creditizie** collegate, con KPI, score, rating, DSCR, PFN/EBITDA e importi sostenibili quando presenti.

### Nuova reportistica documentale v1.3

- riepilogo tabellare per cliente con Tipo documento, Esercizio, Data, Nome documento, Pratica, Origine, Stato verifica e Drive;
- PDF generato al momento direttamente dai record Airtable collegati al cliente;
- layout professionale FinancePlus, A4 orizzontale e multipagina;
- download immediato senza salvare il PDF nel repository;
- tutti i documenti collegati sono inclusi, anche quando un cliente ne possiede decine.

### Funzioni di modifica v1.2

- **Modifica anagrafica cliente** direttamente dalla scheda;
- aggiornamento di Ragione sociale, P.IVA, CF, PEC, email, REA, sede, CAP, Comune, Provincia, forma giuridica, ATECO, attivita, capitale sociale e amministratore;
- aggiornamento di ultima visura, stato verifica, CR aggiornata, ultimo bilancio e note;
- **creazione nuova pratica** direttamente dalla scheda Cliente;
- generazione proposta automatica del `Pratica ID`;
- collegamento automatico della nuova pratica al record Airtable del cliente;
- aggiornamento di pratica esistente: stato, priorita, responsabile, istituto, importo richiesto, scadenza, prossima azione, scadenza prossima azione, stato documentazione, documenti mancanti, alert e note;
- salvataggio immediato su Airtable e refresh della scheda.

L'associazione usa prioritariamente i **linked record Airtable** (`Cliente collegato`) e mantiene un fallback sul campo testuale `Cliente` per compatibilita con i record storici.

## Altre funzioni

- Dashboard con conteggi Clienti, Pratiche, Documenti, Email e alert visure datate.
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

La struttura e relazionale: **Clienti → Pratiche / Documenti / Email / Analisi Creditizie**.

## Deploy su Streamlit Cloud

Usare come entrypoint:

`FinancePlus_Airtable/streamlit_app.py`

Nei **Secrets** della app inserire:

```toml
AIRTABLE_TOKEN = "pat_xxxxxxxxxxxxxxxxx"
AIRTABLE_BASE_ID = "appoNJtS64JIcZUhT"
```

Per usare le funzioni di scrittura il PAT Airtable deve avere accesso **in lettura e scrittura** alla base FinancePlus AI. Le credenziali non devono essere committate in GitHub.

## Architettura

`Streamlit UI -> Airtable REST API -> FinancePlus AI base`

L'app resta separata dal motore analitico FINANCE_PLUS_GOLD ed e un front-end CRM/Airtable dedicato a consultazione, dossier cliente e gestione operativa delle pratiche.
