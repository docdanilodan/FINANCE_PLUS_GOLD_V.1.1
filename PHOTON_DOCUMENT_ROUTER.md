# FinancePlus Document Router + Photon Commerce

## Obiettivo

FinancePlus resta l'orchestratore. L'utente carica o acquisisce un documento una sola volta; il router sceglie automaticamente il motore piu adatto e applica il Data Quality Gate prima di considerare il dato affidabile.

## Politica di routing

- Visure camerali, Centrale Rischi, bilanci e documenti creditizi specialistici: FinancePlus.
- Fatture: Photon come estrattore, FinancePlus come validatore deterministico.
- Estratti conto: Photon quando disponibile, con controllo FinancePlus.
- Ricevute, remittance, B/L e fatture commerciali/trasporto: Photon quando configurato.
- Confidenza 80%-95%: doppio controllo quando il secondo motore e disponibile.
- Confidenza <80%: revisione obbligatoria.
- Photon non configurato, disabilitato o quota sessione esaurita: fallback FinancePlus, senza bloccare l'app.

## Data Quality Gate fatture

Il controllo intercetta almeno:

1. quadratura tra subtotale, imposta, spese, sconti e totale;
2. coerenza della somma delle righe con il subtotale;
3. coerenza della somma righe + imposta con il totale;
4. possibile inversione DD/MM <-> MM/DD confrontando la data Photon con il testo sorgente.

Il test e stato aggiunto dopo una prova reale in cui Photon ha riconosciuto correttamente cliente e totale ma ha invertito la data italiana e ha prodotto una ricostruzione IVA/subtotale incoerente con le righe del documento.

## Configurazione Photon

Non salvare credenziali reali nel repository. Inserire nei Secrets Streamlit/Render:

```toml
PHOTON_AUTO_ENABLED = "true"
PHOTON_ENV = "sandbox"
PHOTON_CLIENT_ID = "..."
PHOTON_USERNAME = "..."
PHOTON_API_KEY = "..."
PHOTON_PASSWORD = "..."
PHOTON_SECRET_KEY = "..."
PHOTON_TIMEOUT_SECONDS = "60"
PHOTON_WAIT_SECONDS = "8"
PHOTON_SESSION_MAX_CALLS = "20"
```

`PHOTON_ENV="production"` usa l'endpoint di produzione. Tenere `sandbox` finche i test non sono chiusi.

## API usata

Il client segue gli esempi pubblici Photon PRO:

- submit: `POST /api/pro?doctype=<tipo>` con multipart `pdf`;
- retrieve: `GET /api/v4/json?photon_key=<key>`;
- header: `CLIENT-ID`, `AUTHORIZATION: apikey username:api_key`, `PASSWORD`, `SECRET-KEY`.

## Sicurezza e costi

- `PHOTON_AUTO_ENABLED=false` impedisce ogni invio esterno anche se le credenziali sono presenti.
- Cache per SHA-256 nella sessione: lo stesso file non viene inviato due volte durante la stessa sessione.
- Limite sessione configurabile con `PHOTON_SESSION_MAX_CALLS`.
- `Raw_Text` Photon non viene mostrato automaticamente nell'interfaccia per evitare output inutilmente estesi.

## Stato integrazione

Il router e collegato alla pagina Document AI dell'entrypoint Streamlit corrente. La stessa libreria `services/document_router.py` e riutilizzabile dalle pipeline Gmail/Drive, WhatsApp e archivio automatico senza duplicare la logica di decisione.
