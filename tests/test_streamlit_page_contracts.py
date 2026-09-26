from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"

PAGE_CONTRACTS = {
    "Dashboard": {"heading": "Centro di controllo MASTER", "minimum": {"metric": 5, "dataframe": 1}},
    "Clienti 360": {"heading": "Cliente 360", "minimum": {"dataframe": 1, "text_input": 1}},
    "Pratiche": {"heading": "Pratiche", "minimum": {"dataframe": 1}},
    "Documenti": {"heading": "Archivio documentale", "minimum": {"dataframe": 1, "file_uploader": 1}},
    "Document AI": {"heading": "Document AI / OCR-IDP", "minimum": {"file_uploader": 1, "text_area": 1}},
    "Bilanci/KPI": {"heading": "Bilanci / KPI / Rating baseline", "minimum": {"number_input": 13, "button": 1}},
    "Centrale Rischi": {"heading": "Centrale Rischi avanzata", "minimum": {"file_uploader": 1}},
    "Conti Correnti": {"heading": "Conti correnti e Cash Flow", "minimum": {"file_uploader": 1, "number_input": 1}},
    "Business Plan": {"heading": "Business Plan 5 anni", "minimum": {"number_input": 10, "button": 1}},
    "PHANTOM / MCC": {"heading": "PHANTOM / PD / MCC", "minimum": {"info": 1}},
    "Ranking operatori": {"heading": "Banche / Fintech / Factor / Confidi", "minimum": {"file_uploader": 1, "warning": 1}},
    "CRM Agenda": {"heading": "CRM — Note, Call, Video Call, Appuntamenti", "minimum": {"dataframe": 1, "selectbox": 4, "text_area": 1}},
    "Mandati": {"heading": "Mandati e compensi", "minimum": {"number_input": 6, "button": 1}},
    "Report / Dossier": {"heading": "Report / Dossier", "minimum": {"info": 1}},
    "Email / Storage / API": {"heading": "Integrazioni", "minimum": {"dataframe": 1}},
    "Impostazioni": {"heading": "Impostazioni / Provenienza / Audit", "minimum": {"code": 1}},
}


def _values(collection) -> list[str]:
    return [str(getattr(item, "value", "")) for item in collection]


def _navigate(app: AppTest, page: str) -> None:
    app.sidebar.radio[0].set_value(page)
    app.run()
    assert not app.exception, f"{page}: exceptions={_values(app.exception)}"
    assert not app.error, f"{page}: Streamlit errors={_values(app.error)}"


def test_every_master_page_meets_its_ui_contract() -> None:
    """Semantic visual/functional gate for every canonical MASTER page.

    This complements the macro smoke test by checking that the expected page
    heading and essential UI controls are actually rendered. It deliberately
    avoids external-service writes and therefore remains deterministic in CI.
    """
    app = AppTest.from_file(APP_PATH, default_timeout=30)
    app.run()
    assert not app.exception, _values(app.exception)

    for page, contract in PAGE_CONTRACTS.items():
        _navigate(app, page)

        headings = _values(app.subheader)
        assert any(contract["heading"] in text for text in headings), (
            page,
            contract["heading"],
            headings,
        )

        for element_type, minimum in contract["minimum"].items():
            rendered = getattr(app, element_type)
            assert len(rendered) >= minimum, (
                f"{page}: expected >= {minimum} {element_type}, got {len(rendered)}"
            )


def test_core_calculators_are_clickable_without_external_credentials() -> None:
    """Exercise the two deterministic calculators exposed directly in the UI."""
    app = AppTest.from_file(APP_PATH, default_timeout=30)
    app.run()

    _navigate(app, "Bilanci/KPI")
    labels = {item.label: item for item in app.number_input}
    values = {
        "Ricavi": 1_000_000.0,
        "EBITDA": 180_000.0,
        "EBIT": 140_000.0,
        "Debito finanziario": 300_000.0,
        "Cassa": 80_000.0,
        "Patrimonio netto": 400_000.0,
        "Attivo corrente": 500_000.0,
        "Passivo corrente": 300_000.0,
        "Totale attivo": 1_200_000.0,
        "CFADS": 150_000.0,
        "Debt service": 90_000.0,
        "Oneri finanziari": 20_000.0,
        "CFO": 160_000.0,
    }
    for label, value in values.items():
        labels[label].set_value(value)
    next(button for button in app.button if button.label == "Calcola analisi").click()
    app.run()
    assert not app.exception, _values(app.exception)
    assert not app.error, _values(app.error)
    assert app.json, "Bilanci/KPI did not render an analysis result"

    _navigate(app, "Business Plan")
    next(button for button in app.button if button.label == "Genera BP").click()
    app.run()
    assert not app.exception, _values(app.exception)
    assert not app.error, _values(app.error)
    assert app.dataframe, "Business Plan did not render a projection table"
