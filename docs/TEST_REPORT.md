# APP_NUOVA_SETT_IA_00 MASTER - Test Report Stage2 RC2

Data aggiornamento: 2026-09-16

## Test automatici locali

Comandi:

```bash
python -m compileall -q app.py financeplus financeplus_cr_engine
pytest -q
```

Esito finale: **14 passed**.

Copertura della suite: quality gate finanziario, massimo finanziabile DSCR-constrained, PHANTOM/MCC fail-safe, cashflow e riconciliazione, Business Plan fallback, ORM/schema, RBAC, Document AI fail-safe, regressioni Stage2 per CR reali ed estratti conto reali.

## Collaudo Stage2 reale

| Area | Stato | Evidenza sintetica |
|---|---|---|
| Neon produzione | IMPLEMENTATO E TESTATO (schema) | preflight a 0 righe sulle tabelle confliggenti; snapshot rollback creato; tabelle MASTER e `pre_master_*` verificate |
| CR 36 mesi | TESTATO SU 3 DATI REALI | copertura quantitativa 33/36, 36/36, 36/36 |
| Estratti conto | TESTATO SU 3 DATI REALI | riconciliazione saldo iniziale + movimenti = saldo finale su tutti i campioni |
| Gmail | TESTATO | ricerca/lettura messaggio e allegato PDF reale |
| Google Drive | TESTATO READ/WRITE | download reali + upload/download controllato con SHA-256 invariato |
| Airtable | TESTATO READ/WRITE | base reale letta; record Documenti di collaudo creato e riletto |
| Gmail -> Drive -> Airtable | TESTATO E2E | allegato Gmail reale archiviato in cartella Drive isolata e indicizzato in Airtable con hash |
| Aruba / PEC | RICHIEDE CREDENZIALI | implementazione IMAP SSL presente; credenziali non disponibili nel runtime e nessun connettore Aruba specifico installato |
| PDF CR | TESTATO | 3 report, 15 pagine, render e controllo visivo |
| PDF dossier bancario | TESTATO SINTETICO | generatore corrente GitHub renderizzato senza errori |
| PDF riepilogo documentale | TESTATO SINTETICO STRESS | 64 righe, 7 pagine, header ripetuti e wrapping verificati visivamente |
| PDF mandato storico | RICHIEDE SORGENTE ORIGINALE | template/generatore canonico storico non materializzato |

## Neon - rollback e preservazione

Prima del cutover e stato creato lo snapshot manuale:

- `pre-master-stage2-prod-20260916`
- snapshot id `snap-late-mode-b2o93xbf`

Le precedenti tabelle confliggenti, risultate vuote al preflight, sono state preservate come:

- `pre_master_clients_20260916`
- `pre_master_practices_20260916`
- `pre_master_documents_20260916`
- `pre_master_mandates_20260916`
- `pre_master_audit_log_20260916`

## Limiti residui

La build non viene dichiarata pienamente GOLD stabile finche non sono completati: login/sync Aruba reale con segreti configurati in ambiente protetto; smoke test dell'app deployata contro `DATABASE_URL` Neon di produzione; parita del mandato PDF storico e delle sorgenti canoniche ancora mancanti; esecuzione CI sul branch GitHub MASTER una volta pubblicata la build.
