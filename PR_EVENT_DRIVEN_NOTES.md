# Event-driven AI pipeline — review notes

## Implemented

- Airtable `Eventi AI` audit log support in adapter.
- Document sensitivity policy and privacy gate.
- FastAPI event ingress with webhook secret validation.
- OpenAI Responses API wrapper.
- CData read-only gateway.
- Airtable Webhooks API client.
- Automatic practice readiness trigger only when documentation is complete.
- AI write-back disabled by default and controlled by `FINANCEPLUS_AI_WRITE_BACK`.
- Privacy classification unit tests.

## External activation still required after merge

1. Deploy `event_api.py` on an HTTPS service.
2. Configure deployment secrets.
3. Configure Airtable Automation or Airtable Webhooks API to call the deployed endpoint.
4. Add real FinancePlus financial data sources to CData Connect AI when available.

No credentials are stored in GitHub.
