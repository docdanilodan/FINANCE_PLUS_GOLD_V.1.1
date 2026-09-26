from __future__ import annotations

def availability() -> dict:
    try:
        import financeplus_cr_engine
        return {"status":"IMPLEMENTATO","engine":"financeplus_cr_engine / CR_2026_2_CORRETTO"}
    except Exception as exc:
        return {"status":"RICHIEDE_SORGENTE_ORIGINALE","error":str(exc)}

def analyze_cr_file(input_path: str, output_pdf: str, audit_json: str | None = None, *, allow_invalid: bool = False):
    from financeplus_cr_engine.pipeline import run
    return run(input_path, output_pdf, audit_json=audit_json, allow_invalid=allow_invalid)
