# FinancePlus 360 AI — Integrazioni 31/08/2026

## Obiettivo
Preparare FinancePlus alle nuove capacità event-driven di Gmail/GitHub/ChatGPT Work e alla gestione di documenti Google Drive con Client-Side Encryption (CSE), mantenendo privacy gate, audit e approvazione umana.

## 1. Webhook esterni
L'Event API espone ora ingressi separati:

```text
POST /events/gmail
POST /events/github
POST /events/work
```

Tutti richiedono:

```text
X-FinancePlus-Webhook-Secret: <FINANCEPLUS_WEBHOOK_SECRET>
```

Payload minimo Gmail/GitHub:

```json
{
  "external_id": "id-esterno",
  "event_type": "evento.tipo",
  "detail": "dettaglio minimo e non sensibile",
  "correlation_id": "opzionale"
}
```

Payload Work:

```json
{
  "source_platform": "Gmail",
  "external_id": "id-esterno",
  "event_type": "message.received",
  "detail": "metadati minimizzati"
}
```

Gli eventi esterni sono audit-only: non modificano Clienti, Pratiche o Documenti senza un successivo flusso esplicitamente autorizzato.

## 2. Audit sorgenti tecniche
La tabella Airtable `Eventi AI` include il campo `Sorgente tecnica`, che registra la sorgente reale (Gmail, GitHub, ChatGPT Work, Google Drive, ecc.) anche quando il vecchio campo `Origine` non contiene una scelta dedicata.

## 3. Google Drive CSE
La tabella `Documenti` include ora:

- `Protezione Drive`: `Standard` / `CSE`
- `Policy elaborazione AI`: `Consentita` / `Solo con approvazione` / `Bloccata`

Regole FinancePlus:

- `CSE` → `Bloccata`
- `Altamente riservato` → `Bloccata`
- `Riservato` → `Solo con approvazione`
- `Interno` + `Standard` → `Consentita`

Il privacy gate ha precedenza su qualsiasi modulo AI.

## 4. Gmail → Drive → Airtable
I nuovi allegati Gmail archiviati dalla pipeline vengono marcati come:

```text
Protezione Drive = Standard
```

La policy AI viene calcolata automaticamente in base alla sensibilità. Nei `appProperties` Drive vengono salvati anche:

```text
financeplusSensitivity
financeplusDocumentType
financeplusSource
financeplusDriveProtection
financeplusAiPolicy
```

## 5. Browser autenticato / ChatGPT Work
Per portali autenticati senza API/MCP, il workflow raccomandato è:

```text
Login eseguito dall'utente → download/lettura autorizzata → staging FinancePlus → SHA-256 → classificazione → privacy gate → Airtable/Drive
```

Vincoli:

- nessuna password o session token nel repository;
- nessuna operazione bancaria/dispositiva automatica;
- documenti CSE o Altamente riservati non vengono inviati automaticamente a servizi AI esterni;
- scritture operative solo tramite staging e approvazione.

## 6. Health check
`GET /health` espone anche:

```text
external_webhooks=true
drive_cse_policy=true
```

Questi flag indicano che il servizio è predisposto alle nuove policy; non attestano da soli che l'account Google abbia CSE abilitato o che i task Work siano configurati nell'interfaccia ChatGPT.
