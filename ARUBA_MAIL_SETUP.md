# Aruba Mail - FINANCE_PLUS_UNICO

Il repository supporta ora due caselle Aruba IMAP aggiuntive oltre alla Gmail principale:

- `d.dangelo@financeplus.tech`
- `pratiche@financeplus.tech`

## Parametri Aruba

- IMAP: `imaps.aruba.it`
- Porta: `993`
- Sicurezza: SSL/TLS

## Streamlit Secrets

Inserire nei Secrets del deploy Streamlit, mai nel repository:

```toml
ARUBA_D_DANGELO_EMAIL = "d.dangelo@financeplus.tech"
ARUBA_D_DANGELO_PASSWORD = "PASSWORD_DELLA_CASELLA"

ARUBA_PRATICHE_EMAIL = "pratiche@financeplus.tech"
ARUBA_PRATICHE_PASSWORD = "PASSWORD_DELLA_CASELLA"
```

Restano necessari anche i Secrets già utilizzati dall'app:

```toml
AIRTABLE_TOKEN = "..."
AIRTABLE_BASE_ID = "appoNJtS64JIcZUhT"
GOOGLE_OAUTH_TOKEN_JSON = "..."
GOOGLE_DRIVE_FOLDER_ID = "..."
```

## Uso

Dopo il redeploy, nella sidebar compare `📨 Aruba Mail`.

1. Selezionare la casella.
2. Premere `🔌 Test`.
3. Se la connessione è OK, scegliere la data iniziale.
4. Premere `🔄 Sincronizza`.

La sincronizzazione usa le stesse regole FinancePlus:

`Aruba IMAP -> allegati -> SHA-256 -> Document AI -> riconoscimento Cliente/Pratica -> Google Drive -> Airtable`

I duplicati sono bloccati tramite SHA-256 e la casella sorgente resta tracciata nel record email/documento.

## Sicurezza

Non salvare password Aruba in file Python, README pubblici, issue GitHub o chat. Le password devono rimanere esclusivamente nei Secrets del deployment.
