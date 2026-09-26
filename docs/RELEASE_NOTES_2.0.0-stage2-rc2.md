# Release notes - APP_NUOVA_SETT_IA_00 MASTER 2.0.0-stage2-rc2

## Cambiamenti rispetto a Stage2 RC1

- eseguito cutover dello schema Neon di produzione dopo preflight e snapshot di rollback;
- preservate le precedenti tabelle vuote con prefisso `pre_master_*_20260916`;
- completato E2E controllato Gmail -> Google Drive -> Airtable con hash SHA-256 invariato e read-back del record;
- estesa la regression PDF al dossier bancario corrente e al riepilogo documentale cliente con stress test multipagina;
- mantenuto fail-safe Aruba/PEC: nessun test di login dichiarato senza credenziali reali;
- suite automatica invariata verde: **14 passed**.

## Stato rilascio

RC2 e adatta alla prosecuzione del collaudo operativo. Non e ancora etichettata GOLD STABILE FINALE per i blocchi espliciti riportati in `docs/TEST_REPORT.md` e `provenance/stage2_status.csv`.
