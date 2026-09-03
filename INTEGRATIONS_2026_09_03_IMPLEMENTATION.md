# FinancePlus 360 AI - integrazioni operative 3 settembre 2026

## Implementato

1. **Drive / Archivio Smart** - resta attiva la classificazione tramite Drive Labels con regola monotona: una label può aumentare la sensibilità, mai ridurla.
2. **Airtable** - il client Webhooks gestisce paginazione fino a 50 payload, cursor drain, refresh e attivazione/disattivazione delle notifiche. Gli ID webhook vengono validati prima di entrare nell'URL.
3. **OpenAI** - nuovo cruscotto costi read-only raggruppato per API key ID e voce di costo, con mapping opzionale verso i moduli FinancePlus.
4. **CData Connect AI** - aggiunti indicatori di readiness per Management API, SIEM e custom instructions. Le chiamate amministrative restano disattivate finché non sono disponibili endpoint e PAT del tenant.
5. **GitHub Actions** - i job Gmail, Aruba e Drive non falliscono più soltanto perché i Secrets non sono ancora presenti. Mostrano un notice e terminano senza installazioni inutili.
6. **Event bridge Gmail** - tre tentativi con timeout; un errore della telemetria non annulla un'archiviazione già riuscita.
7. **Workspace Studio / Acrobat Analyzer** - esposti come pilot governati nelle Impostazioni. Restano disattivati per default fino alla verifica della licenza e delle API disponibili nel tenant.

## Secrets nuovi o aggiornati

```text
OPENAI_ADMIN_KEY
FINANCEPLUS_OPENAI_KEY_LABELS_JSON
CDATA_MANAGEMENT_API_URL
CDATA_ADMIN_PAT
CDATA_SIEM_PROVIDER
CDATA_CUSTOM_INSTRUCTIONS
FINANCEPLUS_WORKSPACE_STUDIO_PILOT=false
FINANCEPLUS_ACROBAT_ANALYZER_PILOT=false
```

Non inserire valori reali nel repository. Configurarli soltanto nei Secrets di Streamlit, Render o GitHub Actions secondo il servizio che deve usarli.

## Attivazione consigliata

1. Configurare le credenziali Airtable/Google già previste.
2. Compilare `FINANCEPLUS_DRIVE_LABEL_MAP_JSON` con gli ID reali delle label/choice del dominio Workspace.
3. Creare chiavi OpenAI separate per modulo e mappare soltanto i relativi ID nel JSON delle etichette.
4. Ottenere dal tenant CData l'endpoint Management API e un PAT amministrativo a privilegi minimi; configurare Datadog o Splunk come SIEM prima di abilitare azioni amministrative.
5. Attivare Workspace Studio e Acrobat Analyzer prima su fascicoli anonimizzati, con approvazione umana obbligatoria e confronto con la pipeline FinancePlus.
