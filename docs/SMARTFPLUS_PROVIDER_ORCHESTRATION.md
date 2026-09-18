# SMART F+ Provider Orchestration

## Target

SMART F+ keeps one operational flow and avoids duplicate systems of record.

```text
Cliente 360
  -> Document Intelligence
  -> Data Quality Gate
  -> financial / cash-flow / CR analysis
  -> KPI / scoring / stress
  -> financing request
  -> Funding Intelligence
  -> CRM / workflow mirror
  -> dossier / reports
  -> audit / backup
```

## Data authority

1. **Neon PostgreSQL** is the preferred cloud system of record.
2. **SQLite** remains the local/offline continuity store.
3. **Airtable** is a compatibility/operational mirror while the web UI is migrated.
4. Attio, monday.com and Asana are workflow/CRM endpoints only. They are not allowed to become a second accounting or credit source of truth.

No automatic data migration is performed by this change.

## Document Intelligence

The provider chain is intentionally replaceable:

- local pypdf extraction;
- Azure AI Document Intelligence (optional structured OCR);
- Adobe PDF Services (optional PDF-to-Markdown);
- Photon Commerce for supported invoice/statement categories;
- FinancePlus Data Quality Gate and human review remain authoritative.

Cloud extraction must respect the existing sensitivity and AI-policy gates. Highly confidential documents remain blocked from automatic external AI processing.

### Azure configuration

```text
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=...
AZURE_DOCUMENT_INTELLIGENCE_KEY=...
AZURE_DOCUMENT_INTELLIGENCE_API_VERSION=2024-11-30
AZURE_DOCUMENT_INTELLIGENCE_MODEL=prebuilt-layout
```

For confidential documents Azure is disabled by default. It can be enabled only through an explicit deployment setting:

```text
FINANCEPLUS_AZURE_ALLOW_CONFIDENTIAL=false
```

## Runtime provider registry

`services/integration_registry.py` exposes a secret-free readiness snapshot used by the Event API health endpoint.

Deployment/API connectivity is deliberately distinguished from ChatGPT plugin connectivity. A plugin being connected to ChatGPT does not make that provider automatically available inside the Windows or Streamlit application.

## Workflow providers

The application recognizes optional bridge configuration for:

```text
FINANCEPLUS_ASANA_BRIDGE_URL
FINANCEPLUS_MONDAY_BRIDGE_URL
FINANCEPLUS_ATTIO_BRIDGE_URL
```

No practice is pushed externally simply because a bridge exists. Writes must remain explicit, auditable and privacy-filtered.

## Rollback

The new provider registry and Azure adapter are additive. Removing their environment variables restores the previous behavior without changing persistent data.
