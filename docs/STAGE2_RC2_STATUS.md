# Stage2 RC2 - stato esecutivo

**Build:** APP_NUOVA_SETT_IA_00 MASTER 2.0.0-stage2-rc2  
**Data:** 16/09/2026

## Completato

- Neon reale: schema MASTER applicato in produzione con snapshot rollback e preservazione delle tabelle precedenti.
- CR 36 mesi: 3 PDF reali.
- Estratti conto: 3 PDF reali con riconciliazione esatta.
- Gmail: allegato reale letto.
- Drive: read/write controllato.
- Airtable: read/write controllato.
- E2E Gmail -> Drive -> Airtable: completato con SHA-256 verificato.
- PDF: CR reale + dossier bancario sintetico + riepilogo documentale stress multipagina.
- Test automatici: 14/14 passed.

## Ancora bloccato

- Aruba/PEC reale: richiede segreti della casella configurati fuori dalla chat.
- PDF mandato storico: richiede il generatore/template originale per una vera regression di parita.
- Runtime deployato: resta da lanciare lo smoke test dell'app contro Neon produzione e poi la CI sul branch MASTER.
