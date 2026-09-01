# Compatibility entry point: use the Web/Desktop aligned master workspace.
from streamlit_desktop_aligned import *  # noqa: F401,F403
from services.aruba_mail_ui import render_aruba_mail_sidebar

render_aruba_mail_sidebar()
