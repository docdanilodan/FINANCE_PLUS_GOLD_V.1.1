# Entry point unico Streamlit Cloud. run_path executes the UI on every
# Streamlit rerun instead of relying on Python's import cache.
import runpy
from pathlib import Path

from services.aruba_mail_ui import render_aruba_mail_sidebar
from services.ui_theme import apply_fp_gold_theme

apply_fp_gold_theme()
runpy.run_path(
    str(Path(__file__).with_name("master_app.py")), run_name="__financeplus_master__"
)
render_aruba_mail_sidebar()
