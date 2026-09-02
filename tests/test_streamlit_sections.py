from __future__ import annotations

from streamlit.testing.v1 import AppTest


def test_streamlit_all_macro_sections_render_without_exceptions() -> None:
    """Smoke-test every macro section of the active Streamlit entrypoint.

    External services are intentionally left unconfigured in CI: each page must
    still render its safe configuration/empty-state UI without crashing.
    """
    app = AppTest.from_file("streamlit_app.py", default_timeout=30)
    app.run()

    assert not app.exception, [str(exc.value) for exc in app.exception]
    assert app.sidebar.radio, "Navigation radio was not rendered"

    navigation = app.sidebar.radio[0]
    options = list(navigation.options)
    expected = {
        "🏠 Dashboard",
        "👥 Clienti 360",
        "💼 Pratiche",
        "📚 Documenti",
        "🤖 Document AI",
        "✉ Email e Drive",
        "📊 Analisi",
        "🏦 Centrale Rischi",
        "💳 Conti Correnti",
        "📈 Business Plan",
        "📄 Report PDF",
        "📝 Mandati",
        "⚙ Impostazioni",
    }
    assert expected.issubset(set(options)), options

    for option in options:
        navigation.set_value(option)
        app.run()
        assert not app.exception, f"Section {option!r} raised: {[str(exc.value) for exc in app.exception]}"
