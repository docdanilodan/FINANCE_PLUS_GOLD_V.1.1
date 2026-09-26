"""UNICO entrypoint Streamlit per APP_NUOVA_SETT_IA_00 MASTER.

Niente exec(compile), niente wildcard import, niente entrypoint concorrenti.
"""
from financeplus.ui import run_app

if __name__ == "__main__":
    run_app()
