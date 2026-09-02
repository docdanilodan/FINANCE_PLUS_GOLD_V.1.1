# FinancePlus Copilot instructions

- Never place real client documents, bank statements, Centrale Rischi data, credentials, OAuth tokens, API keys, passwords, PEC content or personal data in prompts, comments, tests, fixtures or generated code.
- Use synthetic or irreversibly redacted examples. Do not reconstruct removed values.
- Treat `.github/workflows/**`, `.streamlit/**`, authentication, Drive classification, OpenAI access and external integrations as high-risk paths requiring human review.
- An approval assessment is advisory only. Do not treat it as a merge approval and do not enable automated approvals for this repository.
- Preserve the FinancePlus privacy gates: `CSE` and `Altamente riservato` must keep cloud AI processing blocked.
- Never weaken sensitivity, retention, audit, data-quality or secret-handling controls to make a test or deployment pass.
- Actions audit records may contain workflow metadata and failed step names only; never copy raw logs, artifacts, payloads or secrets into the audit branch.
