# Entry point unico Streamlit - F_P_GOLD V_1.1 Web/Desktop aligned.
from pathlib import Path

import streamlit as st

# Execute the shared UI in the actual Streamlit entrypoint context. Importing it
# as a module can leave the deployed frontend with an empty main area even when
# AppTest succeeds locally.
_SHARED_APP = Path(__file__).with_name("streamlit_desktop_aligned.py")
exec(compile(_SHARED_APP.read_text(encoding="utf-8"), str(_SHARED_APP), "exec"), globals(), globals())
from services.aruba_mail_ui import render_aruba_mail_sidebar

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

render_aruba_mail_sidebar()
