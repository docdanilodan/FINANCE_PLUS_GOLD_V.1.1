# FinancePlus 360 AI - integrazioni 31 agosto 2026

## Obiettivo

Integrare le novita tecniche ad alto impatto senza indebolire privacy, audit e approvazione umana.

## 1. Gmail + PDF content-aware

La pipeline Gmail preesistente viene mantenuta come fallback in `services/gmail_drive_pipeline_legacy.py`.
`services/gmail_drive_pipeline.py` e ora un facade compatibile che instrada la sincronizzazione alla pipeline v2.

La v2:

1. scarica l'allegato Gmail;
2. calcola SHA-256 e applica la deduplicazione esistente;
3. estrae localmente il testo PDF con pypdf prima di qualunque elaborazione cloud;
4. classifica tipo documento, sensibilita e policy AI sul contenuto effettivo;
5. se la policy lo consente e Adobe e configurato, usa PDF Services PDF-to-Markdown e riclassifica sul Markdown strutturato;
6. archivia su Drive e registra su Airtable come prima.

I documenti `Altamente riservato` non vengono inviati ad Adobe. I documenti `Riservato` possono usare Adobe solo impostando esplicitamente `FINANCEPLUS_ADOBE_ALLOW_CONFIDENTIAL=true`.

## 2. Google Drive Labels -> FinancePlus policy

`services/drive_classification.py` legge le labels gia applicate a un file con Drive API `files.listLabels`.
FinancePlus non modifica le labels Google.

Configurare:

```text
FINANCEPLUS_DRIVE_LABEL_MAP_JSON={"ID_SCELTA_SEGRETO":"Altamente riservato","ID_SCELTA_RISERVATO":"Riservato","ID_SCELTA_INTERNO":"Interno"}
```

Sono preferibili gli ID stabili delle scelte/field/label anziche i nomi visualizzati.
Una label puo solo aumentare la sensibilita rispetto alla classificazione FinancePlus gia presente; non puo ridurla.

Il workflow `drive_classification_sync.yml` riesamina i file FinancePlus ogni 6 ore per intercettare labels applicate in modo asincrono dopo l'upload e riallinea anche Airtable.

## 3. Adobe PDF Services

Dipendenza aggiunta:

```text
pdfservices-sdk>=4.3,<5
```

Secrets necessari:

```text
PDF_SERVICES_CLIENT_ID
PDF_SERVICES_CLIENT_SECRET
```

Configurazione:

```text
FINANCEPLUS_PDF_EXTRACTOR=auto
FINANCEPLUS_ADOBE_ALLOW_CONFIDENTIAL=false
```

In assenza di credenziali Adobe, FinancePlus continua a funzionare con estrazione locale pypdf.

## 4. Airtable MCP governance

`services/airtable_mcp_policy.py` applica deny-by-default alle azioni agentiche:

- letture: consentite;
- create/update/delete record: staging e approvazione per default;
- modifiche a schema, interfacce e automazioni: sempre approvazione umana;
- write su dati Altamente riservati: bloccato;
- azioni non riconosciute: bloccate.

La Event API v1.4 espone `POST /policy/airtable-mcp` per applicare la policy a un bridge MCP/agente prima dell'esecuzione.

`FINANCEPLUS_AIRTABLE_MCP_RECORD_WRITE=true` puo abilitare write diretti esclusivamente sui dati classificati `Interno`; il default resta `false`.

## 5. OpenAI

La CI impedisce di reintrodurre riferimenti al deprecato Assistants API (`assistants`, `threads/runs`). FinancePlus resta standardizzato sulla Responses API.

## 6. Sicurezza e rollout

Nessun token reale e stato inserito nel repository.
I nuovi moduli restano inattivi o degradano in modo sicuro quando i relativi secrets non sono configurati.
La pipeline legacy e conservata per rollback immediato.

Prima del merge devono passare compilazione e test automatici della pull request.
