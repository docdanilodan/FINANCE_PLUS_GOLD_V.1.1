# FinancePlus 360 AI — Integrazioni 30/08/2026

## Obiettivo
Integrare in modo operativo le novità più utili per FinancePlus senza ridurre i controlli su dati finanziari e documenti sensibili.

## 1. Gmail / Google multi-account
La pipeline supporta più profili OAuth Google nello stesso deploy.

Profili previsti:
- `DEFAULT` → `GOOGLE_OAUTH_TOKEN_JSON`
- `STUDIO` → `GOOGLE_OAUTH_TOKEN_JSON_STUDIO`
- `PRATICHE` → `GOOGLE_OAUTH_TOKEN_JSON_PRATICHE`

È possibile dichiarare l'ordine con:

```text
FINANCEPLUS_GOOGLE_PROFILES=DEFAULT,STUDIO,PRATICHE
```

Ogni profilo può avere una cartella Drive distinta:

```text
GOOGLE_DRIVE_FOLDER_ID
GOOGLE_DRIVE_FOLDER_ID_STUDIO
GOOGLE_DRIVE_FOLDER_ID_PRATICHE
```

Se manca una cartella specifica, viene usata la cartella Drive predefinita.

## 2. Google Drive: classificazione privacy
Quando un allegato Gmail viene archiviato, FinancePlus salva nei `appProperties` Drive:
- `financeplusSensitivity`
- `financeplusDocumentType`
- `financeplusSource`

La stessa sensibilità viene scritta nel campo Airtable `Sensibilità dati`.

Regole principali:
- Centrale Rischi / Estratto conto → `Altamente riservato`
- Bilancio / Situazione contabile / Contratto / Fattura → `Riservato`
- Visura / DURC / Preventivo / altri → `Interno`

I documenti `Altamente riservato` restano bloccati dal privacy gate per l'invio automatico a servizi AI esterni.

## 3. Airtable: staging delle modifiche AI
È stata aggiunta la tabella `Proposte AI`.

Flusso:
1. FinancePlus genera una raccomandazione.
2. La raccomandazione viene salvata come `Da approvare`.
3. Nessun dato operativo viene sovrascritto automaticamente.
4. Un revisore porta la proposta a `Approvata`.
5. Un evento Airtable verso FinancePlus applica la proposta solo se il campo è nella allowlist.
6. La proposta passa ad `Applicata` e l'operazione viene registrata in `Eventi AI`.

Campi autorizzati iniziali:
- Pratiche: `Prossima azione`, `Alert e criticità`, `Documenti mancanti`
- Documenti: `Nome Definitivo`, `Sintesi IA`, `Stato Verifica`
- Email: `Sintesi IA`, `Priorità`, `Azione Richiesta`
- Clienti: `Note`
- Analisi Creditizie: `Punti di Forza`, `Criticità`, `Raccomandazione IA`

## 4. Variabili consigliate

```text
FINANCEPLUS_AI_STAGING=true
FINANCEPLUS_AI_WRITE_BACK=false
```

Lo staging ha precedenza sul write-back diretto.

## 5. Endpoint eventi

```text
POST /events/airtable
```

Entità supportate:
- Clienti
- Pratiche
- Documenti
- Email
- Analisi Creditizie
- Proposte AI

Header richiesto:

```text
X-FinancePlus-Webhook-Secret: <secret>
```

## 6. Nota operativa
Le funzionalità account-level di Google Drive/ChatGPT che richiedono attivazione nell'account Google o nella UI non possono essere abilitate dal repository. Il codice FinancePlus è però predisposto per multi-account, classificazione privacy, archiviazione e audit.
