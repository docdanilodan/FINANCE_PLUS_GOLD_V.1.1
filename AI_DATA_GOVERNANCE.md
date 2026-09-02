# FinancePlus 360 AI - governance Copilot, CSE e audit

## Regole operative

1. Copilot e gli altri coding agent ricevono esclusivamente codice e dati sintetici o anonimizzati.
2. È vietato inserire in chat, issue, PR o log: credenziali, token OAuth, API key, password, documenti cliente, dati bancari, Centrale Rischi, PEC e dati personali reali.
3. L'assessment Copilot è un parere informativo e non sostituisce l'approvazione umana.
4. L'approvazione automatica Copilot resta disabilitata. Workflow, autenticazione, sicurezza, CSE e integrazioni richiedono sempre revisione umana.
5. I documenti `CSE` si aprono soltanto tramite il link HTTPS di Google Drive. FinancePlus non scarica, non incorpora e non invia il contenuto a servizi AI cloud; la policy resta `Bloccata`.
6. Lo storico Actions conserva esclusivamente metadati già visibili su GitHub: esito, SHA, workflow, job e step. Non conserva log grezzi, artifact o payload applicativi.

## Configurazione amministrativa da completare

- **Google Workspace:** richiedere l'accesso alla beta CSE se la licenza è idonea. Senza abilitazione del dominio, il comando FinancePlus apre Drive ma l'anteprima protetta potrebbe non essere disponibile.
- **GitHub Copilot Code Review:** usare l'assessment incluso nella review; lasciare disattivata l'opzione che consente a Copilot di inviare una vera approval.
- **Branch protection:** richiedere CI superata e almeno una revisione umana. Applicare CODEOWNERS ai percorsi ad alto rischio.
- **Copilot unified experience:** prima del 28 settembre 2026 riesaminare la policy `Copilot cloud agent`. Se non è compatibile con la conservazione delle chat per la vita dell'account, disabilitarla per il repository/team.
- **Actions retention:** lo storico persistente è scritto nel branch `audit/actions-history`. Verificarne la creazione dopo il primo workflow completato.

## Verifica periodica

- controllare che le PR mostrino l'assessment ma non una approval automatica;
- verificare che `CSE` e `Altamente riservato` continuino a produrre `Policy elaborazione AI = Bloccata`;
- confrontare ogni workflow completato con il relativo JSON nel branch di audit;
- riesaminare trimestralmente accessi, policy Copilot e contenuto dello storico.
