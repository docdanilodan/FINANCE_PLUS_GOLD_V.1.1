# Compatibility entry point for old FinancePlus Airtable deploys.
# All deployments now open the same unified master application.
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.aruba_mail_ui import render_aruba_mail_sidebar  # noqa: E402
from services.ui_theme import apply_fp_gold_theme  # noqa: E402

apply_fp_gold_theme()
runpy.run_path(str(ROOT / "master_app.py"), run_name="__financeplus_master__")
render_aruba_mail_sidebar()
