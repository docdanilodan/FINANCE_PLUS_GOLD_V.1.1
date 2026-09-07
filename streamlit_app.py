# Entry point unico Streamlit - F_P_GOLD V_1.1 Web/Desktop aligned.
import os
from pathlib import Path

import streamlit as st

from services.drive_classification import load_drive_label_mapping


def _validated_drive_label_readiness() -> bool:
    """Return readiness only when the configured label map parses to usable entries.

    Streamlit Cloud keeps the mapping in st.secrets while the shared Drive
    classification service reads the environment. Mirror the same raw value
    into the environment, then delegate validation to the production parser so
    the readiness indicator cannot be green for {}, malformed JSON or labels
    outside the supported sensitivity set.
    """
    try:
        raw = str(st.secrets.get("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", "") or "")
    except Exception:
        raw = ""
    raw = raw or os.getenv("FINANCEPLUS_DRIVE_LABEL_MAP_JSON", "")
    if raw:
        os.environ["FINANCEPLUS_DRIVE_LABEL_MAP_JSON"] = raw
    return bool(load_drive_label_mapping())


# Execute the shared UI in the actual Streamlit entrypoint context. Importing it
# as a module can leave the deployed frontend with an empty main area even when
# AppTest succeeds locally.
_SHARED_APP = Path(__file__).with_name("streamlit_desktop_aligned.py")
_SHARED_SOURCE = _SHARED_APP.read_text(encoding="utf-8")
_DRIVE_LABELS_READY = _validated_drive_label_readiness()
_READINESS_EXPRESSION = 'drive_labels = bool(PROFILES and secret("FINANCEPLUS_DRIVE_LABEL_MAP_JSON"))'
if _READINESS_EXPRESSION in _SHARED_SOURCE:
    _SHARED_SOURCE = _SHARED_SOURCE.replace(
        _READINESS_EXPRESSION,
        "drive_labels = bool(PROFILES and _DRIVE_LABELS_READY)",
        1,
    )
exec(compile(_SHARED_SOURCE, str(_SHARED_APP), "exec"), globals(), globals())

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
