# SMART F+ Mobile Cloud 24/7

Runtime HTTPS della companion iOS, collegato allo stesso **Neon PostgreSQL FinancePlus Cloud**.

## Confini

- Nessun secondo database core.
- Cliente 360, pratiche e metadati documentali sono letti da Neon.
- Autenticazione dispositivo tramite hash delle credenziali gia autorizzate.
- SERAFINO 2.1 Cloud: navigazione deterministica, chat Mistral e learning `PROPOSAL_ONLY`.
- Modifiche critiche non vengono eseguite senza un flusso di conferma esplicita.
- I file binari non vengono salvati in Neon.

## Variabili runtime

Obbligatorie in produzione, da inserire nel secret store del provider e mai nel repository:

- `DATABASE_URL` — connessione Neon al database `financeplus`.
- `MISTRAL_API_KEY`.

Non sensibili:

- `MISTRAL_MODEL=mistral-small-latest`.
- `ALLOWED_HOSTS=*.onrender.com`.

## Stato storage documenti

I metadati documentali possono essere sincronizzati su Neon. Upload e preview dei file fisici restano disabilitati finche non e configurato uno storage privato permanente. L'API risponde esplicitamente con `CLOUD_STORAGE_REQUIRED` / `DOCUMENT_BINARY_NOT_CLOUD` invece di simulare il successo.

## Avvio

```bash
pip install -r mobile_cloud/requirements.txt
uvicorn mobile_cloud.app:app --host 0.0.0.0 --port 8000
```

Il servizio puo avviarsi anche senza segreti per consentire il deploy iniziale; in tale stato `/health` dichiara `database_ready=false` e le route protette restano chiuse.
