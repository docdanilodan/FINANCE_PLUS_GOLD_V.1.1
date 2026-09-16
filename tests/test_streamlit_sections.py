from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_all_macro_sections_render_without_exceptions() -> None:
    """Smoke-test every macro section of the canonical MASTER entrypoint.

    External services are intentionally left unconfigured in CI: each page must
    render its safe configuration/empty-state UI without crashing.
    """
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(app_path, default_timeout=30)
    app.run()

    assert not app.exception, [str(exc.value) for exc in app.exception]
    assert app.sidebar.radio, "Navigation radio was not rendered"

    navigation = app.sidebar.radio[0]
    options = list(navigation.options)
    expected = {
        "Dashboard",
        "Clienti 360",
        "Pratiche",
        "Documenti",
        "Document AI",
        "Bilanci/KPI",
        "Centrale Rischi",
        "Conti Correnti",
        "Business Plan",
        "PHANTOM / MCC",
        "Ranking operatori",
        "CRM Agenda",
        "Mandati",
        "Report / Dossier",
        "Email / Storage / API",
        "Impostazioni",
    }
    assert expected == set(options), options

    for option in options:
        navigation.set_value(option)
        app.run()
        assert not app.exception, f"Section {option!r} raised: {[str(exc.value) for exc in app.exception]}"
