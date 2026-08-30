# FinancePlus 360 AI — Event Driven Setup

Questa estensione aggiunge un event layer separato alla Streamlit app esistente.

## Cosa aggiunge

- ingresso eventi HTTP con FastAPI (`event_api.py`);
- audit persistente nella tabella Airtable `Eventi AI`;
- classificazione automatica della sensibilità documentale;
- privacy gate: i documenti `Altamente riservato` non vengono inviati automaticamente a servizi AI esterni;
- analisi automatica di una pratica solo quando `Stato documentazione = Completa`;
- gateway OpenAI basato su Responses API;
- gateway CData Connect AI read-only;
- client per Airtable Webhooks API;
- write-back AI disattivato di default.

## Secrets richiesti

Configurare nel servizio che ospita `event_api.py`:

```text
AIRTABLE_TOKEN
AIRTABLE_BASE_ID=appoNJtS64JIcZUhT
FINANCEPLUS_WEBHOOK_SECRET
OPENAI_API_KEY
OPENAI_MODEL=gpt-5
```

Opzionali per CData:

```text
CDATA_USER
CDATA_PAT
CDATA_BASE_URL=https://cloud.cdata.com
```

Per consentire all'AI di scrivere la raccomandazione nel campo `Prossima azione` della pratica:

```text
FINANCEPLUS_AI_WRITE_BACK=true
```

Il valore di default è `false`.

## Avvio del servizio eventi

```bash
uvicorn event_api:app --host 0.0.0.0 --port 8000
```

Health check:

```text
GET /health
```

## Evento normalizzato

Endpoint:

```text
POST /events/airtable
```

Header obbligatorio:

```text
X-FinancePlus-Webhook-Secret: <secret>
```

Payload:

```json
{
  "entity": "Pratiche",
  "record_id": "recXXXXXXXXXXXXXX",
  "event_type": "record.changed"
}
```

Entità supportate:

- `Clienti`
- `Pratiche`
- `Documenti`
- `Email`
- `Analisi Creditizie`

## Collegamento Airtable

Sono supportati due approcci.

### 1. Airtable Automation

Usare un trigger su creazione/modifica record e inviare all'endpoint FinancePlus l'entità e il record ID. È il percorso più semplice per rendere operativo il flusso.

### 2. Airtable Webhooks API

`services/airtable_webhooks.py` contiene il client per creare, elencare, leggere i payload, aggiornare e cancellare webhook. La `specification` viene passata integralmente all'API Airtable, così filtri e scope possono essere modificati senza cambiare il codice FinancePlus.

## Regole privacy documenti

| Tipo | Sensibilità automatica |
|---|---|
| Centrale Rischi | Altamente riservato |
| Estratto conto | Altamente riservato |
| Dichiarazione fiscale | Altamente riservato |
| Documento identità | Altamente riservato |
| Bilancio | Riservato |
| Situazione contabile | Riservato |
| Contratto | Riservato |
| Fattura | Riservato |
| Atto societario | Riservato |
| Visura camerale | Interno |
| DURC | Interno |
| Preventivo | Interno |

## Flusso operativo

```text
Airtable / Gmail / Drive
        ↓
FinancePlus Event API
        ↓
Event Orchestrator
        ↓
Privacy Gate + Audit
        ↓
Airtable record / OpenAI Responses / CData
        ↓
Eventi AI + eventuale Prossima azione
```

## Sicurezza

- nessuna chiave API viene salvata nel repository;
- CData è configurato come gateway `SELECT`-only nel codice FinancePlus;
- il webhook richiede un secret dedicato;
- gli eventi memorizzano metadati operativi, non il contenuto completo dei documenti;
- i documenti altamente riservati sono bloccati prima dell'invio automatico all'AI;
- il write-back AI è opt-in.

## Stato CData attuale

Il layer è pronto per nuove connessioni CData. Le fonti finanziarie reali vanno collegate in CData Connect AI e autorizzate con il principio del minimo privilegio. Una volta aggiunte, non è necessario modificare l'orchestratore: basta aggiungere il mapping/query del nuovo datasource nel modulo specifico FinancePlus.
