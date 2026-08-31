from __future__ import annotations
import streamlit as st


def apply_fp_gold_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --fp-blue:#06356d;
          --fp-blue-2:#0b4f91;
          --fp-gold:#d6a33a;
          --fp-bg:#f5f7fa;
          --fp-border:#dfe5ec;
        }
        .stApp { background: var(--fp-bg); }
        section[data-testid="stSidebar"] { background: linear-gradient(180deg,#052e63 0%,#073d78 100%); }
        section[data-testid="stSidebar"] * { color: #fff; }
        section[data-testid="stSidebar"] [role="radiogroup"] label { border-radius:8px; padding:6px 8px; }
        section[data-testid="stSidebar"] [role="radiogroup"] label:hover { background:rgba(255,255,255,.10); }
        h1,h2,h3 { color: var(--fp-blue); letter-spacing:-.01em; }
        [data-testid="stMetric"] { background:white; border:1px solid var(--fp-border); border-radius:12px; padding:14px; box-shadow:0 1px 3px rgba(15,45,80,.05); }
        [data-testid="stDataFrame"], [data-testid="stTable"] { background:white; border-radius:10px; border:1px solid var(--fp-border); }
        .stButton>button, .stDownloadButton>button { border-radius:8px; border:1px solid #0b4f91; font-weight:600; }
        .stButton>button[kind="primary"], .stDownloadButton>button:hover { background:var(--fp-blue-2); color:white; }
        [data-baseweb="tab-list"] { gap:4px; }
        [data-baseweb="tab"] { background:white; border:1px solid var(--fp-border); border-radius:8px 8px 0 0; }
        [data-baseweb="tab"][aria-selected="true"] { color:var(--fp-blue); border-bottom:3px solid var(--fp-blue); }
        div[data-testid="stExpander"] { background:white; border:1px solid var(--fp-border); border-radius:10px; }
        .fp-gold-brand { font-weight:800; color:var(--fp-gold); letter-spacing:.08em; }
        </style>
        """,
        unsafe_allow_html=True,
    )
