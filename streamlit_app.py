# Entry point unico Streamlit - F_P_GOLD V_1.1 Web/Desktop aligned.
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from services.document_router import decide_route, invoice_quality_gate
from services.photon_commerce import PhotonCommerceClient, PhotonConfig, PhotonError

# Execute the shared UI in the actual Streamlit entrypoint context. Importing it
# as a module can leave the deployed frontend with an empty main area even when
# AppTest succeeds locally.
_SHARED_APP = Path(__file__).with_name("streamlit_desktop_aligned.py")
exec(compile(_SHARED_APP.read_text(encoding="utf-8"), str(_SHARED_APP), "exec"), globals(), globals())


def _fp_secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.getenv(name, default) or "")


def _photon_config() -> PhotonConfig | None:
    values = {
        "client_id": _fp_secret("PHOTON_CLIENT_ID"),
        "username": _fp_secret("PHOTON_USERNAME"),
        "api_key": _fp_secret("PHOTON_API_KEY"),
        "password": _fp_secret("PHOTON_PASSWORD"),
        "secret_key": _fp_secret("PHOTON_SECRET_KEY"),
    }
    if not all(values.values()):
        return None
    return PhotonConfig(
        **values,
        environment=_fp_secret("PHOTON_ENV", "sandbox").lower() or "sandbox",
        timeout_seconds=int(_fp_secret("PHOTON_TIMEOUT_SECONDS", "60") or 60),
    )


def _photon_enabled() -> bool:
    return _fp_secret("PHOTON_AUTO_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _render_automatic_document_router() -> None:
    """Run immediately after the existing Document AI analysis button.

    The shared app creates the global variable ``rows`` only when the operator
    clicked Analizza, so this hook does not create duplicate API calls on idle
    Streamlit reruns. Results are cached by SHA-256 inside the session.
    """
    if globals().get("page") != globals().get("DOC_AI"):
        return
    if "rows" not in globals():
        return

    current_uploads = globals().get("uploads") or []
    if not current_uploads:
        return

    config = _photon_config()
    enabled = bool(config and _photon_enabled())
    max_calls = max(0, int(_fp_secret("PHOTON_SESSION_MAX_CALLS", "20") or 20))
    calls_used = int(st.session_state.get("_fp_photon_calls", 0) or 0)
    cache: dict[str, dict] = st.session_state.setdefault("_fp_photon_router_cache", {})
    client = PhotonCommerceClient(config) if enabled and config else None

    st.markdown("### Instradamento automatico FinancePlus / Photon")
    if not config:
        st.info("Photon API non configurata: FinancePlus resta operativo in fallback automatico.")
    elif not _photon_enabled():
        st.info("Credenziali Photon presenti, ma PHOTON_AUTO_ENABLED=false: nessun documento viene inviato a Photon.")

    routing_rows: list[dict] = []
    details: list[tuple[str, dict]] = []

    for uploaded in current_uploads:
        raw = uploaded.getvalue()
        sha = hashlib.sha256(raw).hexdigest()
        filename = uploaded.name
        text, local_warning = globals()["extract_text"](uploaded)
        pasted_text = str(globals().get("pasted") or "")
        source_text = (text + "\n" + pasted_text).strip()
        classification = globals()["classify_text"]((filename + "\n" + source_text)[:120000])

        company_value = str(globals().get("company") or "").strip()
        year_value = int(globals().get("year") or 0)
        if company_value:
            classification.company_name = company_value
        if year_value:
            classification.document_year = year_value

        budget_remaining = max_calls - calls_used if enabled else None
        route = decide_route(
            classification.category,
            classification.confidence,
            photon_configured=enabled,
            photon_budget_remaining=budget_remaining,
        )

        status = "FinancePlus"
        quality = "OK"
        issues: list[str] = list(route.warnings)
        photon_key = ""
        photon_data: dict = {}

        should_call = route.primary_engine == "Photon" and client is not None
        if should_call:
            cached = cache.get(sha)
            if cached:
                photon_result = cached
                status = "Photon (cache)"
            else:
                try:
                    photon_result = client.process_bytes(
                        raw,
                        filename,
                        doctype=route.photon_doctype,
                        wait_seconds=float(_fp_secret("PHOTON_WAIT_SECONDS", "8") or 8),
                    )
                    cache[sha] = photon_result
                    calls_used += 1
                    st.session_state["_fp_photon_calls"] = calls_used
                    status = "Photon"
                except PhotonError as exc:
                    photon_result = {"status": "error", "data": {}, "error": str(exc)}
                    status = "Fallback FinancePlus"
                    issues.append(f"Photon: {exc}")

            photon_key = str(photon_result.get("photon_key") or "")
            photon_data = photon_result.get("data") or {}
            if photon_result.get("status") == "queued":
                quality = "IN ATTESA"
                issues.append("Photon ha accodato il documento; risultato non ancora disponibile.")
            elif photon_result.get("status") == "extracted":
                if classification.category == "Fattura":
                    ok, gate_issues = invoice_quality_gate(photon_data, source_text)
                    issues.extend(gate_issues)
                    quality = "OK" if ok else "DA VERIFICARE"
                elif route.needs_human_review:
                    quality = "DA VERIFICARE"
            else:
                quality = "DA VERIFICARE"

        elif route.needs_human_review:
            quality = "DA VERIFICARE"

        if local_warning:
            issues.append(local_warning)

        routing_rows.append(
            {
                "File": filename,
                "Tipo": classification.category,
                "Confidenza": round(float(classification.confidence), 3),
                "Motore": route.engine_label if should_call else status,
                "Photon doctype": route.photon_doctype or "-",
                "Quality Gate": quality,
                "Revisione": "SI" if (route.needs_human_review or quality == "DA VERIFICARE") else "NO",
                "Photon key": photon_key or "-",
                "Motivo": route.reason,
                "Anomalie": " | ".join(dict.fromkeys(issues)) if issues else "-",
            }
        )
        if photon_data:
            details.append((filename, photon_data))

    st.dataframe(pd.DataFrame(routing_rows), use_container_width=True, hide_index=True)
    st.caption(f"Chiamate Photon nella sessione: {calls_used}/{max_calls}. Cache SHA-256 attiva per evitare riinvii dello stesso file.")

    for filename, photon_data in details:
        with st.expander(f"Dati Photon - {filename}"):
            visible = {k: v for k, v in photon_data.items() if k != "Raw_Text"}
            st.json(visible)


_render_automatic_document_router()

# Mobile safety navigation: Streamlit collapses the sidebar automatically on small screens.
# Keep both the native reopen control and a persistent Menu Principale shortcut visible.
st.markdown(
    """
    <style>
    @media (max-width: 900px) {
      [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        position: fixed !important;
        top: .55rem !important;
        left: .55rem !important;
        z-index: 1000000 !important;
        background: #0B1F3A !important;
        border: 1px solid rgba(255,255,255,.22) !important;
        border-radius: 10px !important;
        box-shadow: 0 3px 14px rgba(0,0,0,.22) !important;
      }
      [data-testid="stSidebarCollapsedControl"] * {
        color: white !important;
        fill: white !important;
      }
      .fp-mobile-menu {
        position: fixed;
        right: 14px;
        bottom: 18px;
        z-index: 999999;
        background: #0B1F3A;
        color: #fff !important;
        border: 2px solid #C46B32;
        border-radius: 999px;
        padding: 11px 16px;
        font-weight: 800;
        text-decoration: none !important;
        box-shadow: 0 5px 18px rgba(0,0,0,.24);
      }
    }
    @media (min-width: 901px) {
      .fp-mobile-menu { display: none; }
    }
    </style>
    <a class="fp-mobile-menu" href="/" target="_self">☰ MENU PRINCIPALE</a>
    """,
    unsafe_allow_html=True,
)

# Aruba remains available inside the dedicated Email/Drive area.
# Do not append a second global sidebar panel: on iPhone it obscures the main navigation.
