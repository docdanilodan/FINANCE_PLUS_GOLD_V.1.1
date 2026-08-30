# Event API security controls

- Secret header authentication is mandatory for event ingestion.
- Credentials remain in deployment secrets only.
- CData gateway accepts SELECT statements only.
- Highly confidential document types are blocked from automatic external AI processing.
- AI write-back is disabled unless explicitly enabled.
- Airtable `Eventi AI` stores operational audit metadata and correlation IDs.
