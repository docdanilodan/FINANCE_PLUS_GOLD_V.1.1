# SMART F+ Fase 3 — Airtable → Neon staging

## Stato

**BLOCKED per cutover.** Lo staging è stato creato e validato, ma non viene promosso sul branch Neon di default finché il perimetro documentale non è riconciliato.

## Sorgente e backup

- Sorgente: Airtable **FinancePlus AI**.
- Backup logico separato: **FinancePlus AI BACKUP 2026-09-18 PRE_NEON**.
- Snapshot: **421/421 record**.
- Chiavi snapshot duplicate: **0**.
- ID sorgente mancanti nel backup: **0**.
- Schema sorgente: **7 tabelle**, serializzato nel metadata del backup.
- Open/read check: superato su Clienti, Pratiche, Documenti, Email e Analisi Creditizie.
- Nessuna cancellazione o modifica dei record della base sorgente.

## Destinazione di staging

Neon project `dry-scene-59065763`, branch isolato:

`migration-airtable-staging-20260918` / `br-morning-tree-b2aii623`

Il branch Neon di default non è stato modificato.

| Asset | Sorgente | Staging | Esito |
|---|---:|---:|---|
| Clienti | 97 | 97 | verificato |
| Pratiche | 9 | 9 | verificato |
| Documenti | 293 | 256 | **bloccato** |
| Analisi Creditizie | 6 | 6 | verificato |

Totale importi richiesti Pratiche: **EUR 5.500.000** sia in Airtable sia nello staging Neon.

## Integrità

- Foreign key orfane: **0**.
- SHA-256 duplicati nello staging: **0**.
- SHA-256 con formato non valido nello staging: **0**.
- Checksum mismatch noti: **0**.
- Sequence documenti riallineata a **256**.

## Recupero documenti

Sei documenti che in Airtable erano privi di SHA-256 sono stati recuperati tramite corrispondenza esatta su Google Drive. I file sono stati scaricati in sola lettura e l'hash SHA-256 è stato calcolato sui byte reali; nessun hash è stato derivato dal nome file.

## Review queue

Restano **37 record documentali** non importati nel core:

- **28** senza SHA-256 verificabile;
- **9** senza associazione univoca a Cliente 360.

Sono registrati nello staging in `audit_log` con action `migration_review_required`. Nessuna associazione cliente è stata inventata.

## Guard

`migration_guard.py` restituisce **BLOCKED** per:

1. asset Documenti bloccato;
2. mismatch critico Documenti 293 → 256.

Warning: smoke test applicativo non eseguito, coerentemente con uno staging non completo.

## Rollback

Rollback immediato: Airtable resta intatto e autorevole. Lo staging Neon è un branch isolato e può essere abbandonato senza modificare il default branch.

## Dipendenze applicative

Il cutover dati deve avvenire solo dopo l'accettazione delle PR applicative #25 e #26 e dopo la riconciliazione dei 37 documenti residui. Nessun merge/cutover automatico viene eseguito da questa fase.
