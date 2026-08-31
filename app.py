# Compatibility entry point: the repository now exposes one master application.
from master_app import *  # noqa: F401,F403
from services.ui_theme import apply_fp_gold_theme
from services.aruba_mail_ui import render_aruba_mail_sidebar

apply_fp_gold_theme()
render_aruba_mail_sidebar()
