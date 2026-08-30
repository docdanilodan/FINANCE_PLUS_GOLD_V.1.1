# Deploy Event API

Deploy the repository as a separate service with:

```bash
uvicorn event_api:app --host 0.0.0.0 --port $PORT
```

Required environment variables:

```text
AIRTABLE_TOKEN
AIRTABLE_BASE_ID
FINANCEPLUS_WEBHOOK_SECRET
```

Recommended:

```text
OPENAI_API_KEY
OPENAI_MODEL=gpt-5
```

Optional:

```text
CDATA_USER
CDATA_PAT
CDATA_BASE_URL=https://cloud.cdata.com
FINANCEPLUS_AI_WRITE_BACK=false
```

After deploy, verify `/health`, then connect Airtable Automation or the Airtable Webhooks API client to `/events/airtable`.
