# Entry point unico Streamlit Cloud - FINANCE_PLUS_UNICO V_1.1.
# La logica resta in master_app.py; qui applichiamo il branding release senza duplicare il codice.
import streamlit as st

RELEASE_NAME = "FINANCE_PLUS_UNICO V_1.1"

_orig_set_page_config = st.set_page_config
_orig_title = st.title
_orig_markdown = st.markdown


def _brand_text(value):
    if not isinstance(value, str):
        return value
    return (
        value.replace("FINANCE_PLUS_UNICO V_1.0", RELEASE_NAME)
        .replace("### F_P_UNICO", "### F_P_UNICO V_1.1")
    )


def _set_page_config(*args, **kwargs):
    if "page_title" in kwargs:
        kwargs["page_title"] = _brand_text(kwargs["page_title"])
    elif args:
        args = (_brand_text(args[0]), *args[1:])
    return _orig_set_page_config(*args, **kwargs)


def _title(body, *args, **kwargs):
    return _orig_title(_brand_text(body), *args, **kwargs)


def _markdown(body, *args, **kwargs):
    return _orig_markdown(_brand_text(body), *args, **kwargs)


st.set_page_config = _set_page_config
st.title = _title
st.markdown = _markdown

try:
    import master_app  # noqa: F401
finally:
    st.set_page_config = _orig_set_page_config
    st.title = _orig_title
    st.markdown = _orig_markdown

from services.aruba_mail_ui import render_aruba_mail_sidebar

render_aruba_mail_sidebar()
