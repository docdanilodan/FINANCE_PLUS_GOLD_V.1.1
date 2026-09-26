from __future__ import annotations

SOURCE_MAP = {
    "ui_shell": {"source": "GitHub streamlit_desktop_aligned.py", "version": "ae53f82", "status": "VERIFICATA"},
    "document_ai": {"source": "document_ai.py + services/document_router.py", "version": "ae53f82", "status": "VERIFICATA/PARZIALE"},
    "cr_36m": {"source": "financeplus_cr_engine/*", "version": "CR_2026_2_CORRETTO / ae53f82", "status": "VERIFICATA CODICE"},
    "cashflow_ingestion": {"source": "WEB_APP_CC_VALUE_UNICO_CORRETTO.py", "version": "3.1 / 13-07-2026", "status": "VERIFICATA FILE LIBRARY"},
    "business_plan": {"source": "BPlan_Manager_Premium_Bancario_360.py", "version": "18-06-2026 reference", "status": "RICHIEDE SORGENTE ORIGINALE; fallback MASTER disponibile"},
    "phantom": {"source": "phantom_suite_top.py", "version": "06-06-2026 reference", "status": "RICHIEDE SORGENTE ORIGINALE + CALIBRAZIONE"},
    "matcher": {"source": "FinancePlus Credit Matcher AI PRO", "version": "2026.09 FINAL", "status": "MANUALE VERIFICATO; CATALOGO SORGENTE RICHIESTO"},
    "crm_agenda": {"source": "WEB APP 06_07", "version": "06-07-2026", "status": "MANUALE VERIFICATO; CODICE ORIGINALE RICHIESTO"},
    "gmail": {"source": "services/gmail_drive_pipeline_v2.py", "version": "ae53f82", "status": "VERIFICATA CODICE"},
    "aruba": {"source": "services/aruba_imap_pipeline.py", "version": "ae53f82", "status": "VERIFICATA CODICE"},
    "airtable": {"source": "services/airtable_adapter.py", "version": "ae53f82", "status": "VERIFICATA CODICE"},
    "fascicolo_cliente": {"source": "FinancePlus_Airtable/client_fascicolo.py", "version": "ae53f82", "status": "VERIFICATA CODICE"},
}

def provenance_for(feature: str) -> dict:
    return dict(SOURCE_MAP.get(feature, {"source": "", "version": "", "status": "NON MAPPATA"}))
