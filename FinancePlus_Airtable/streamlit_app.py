# Compatibility entry point for old FinancePlus Airtable deploys.
# All deployments now open FINANCE_PLUS_UNICO V_1.1 Web/Desktop aligned.
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from streamlit_desktop_aligned import *  # noqa: F401,F403,E402
from services.aruba_mail_ui import render_aruba_mail_sidebar  # noqa: E402

render_aruba_mail_sidebar()
