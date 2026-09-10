from services.document_router import decide_route, invoice_quality_gate


def test_visura_stays_financeplus():
    route = decide_route("Visura Camerale", 0.99, photon_configured=True)
    assert route.primary_engine == "FinancePlus"
    assert route.photon_doctype == ""


def test_invoice_routes_to_photon_with_financeplus_gate():
    route = decide_route("Fattura", 0.97, photon_configured=True)
    assert route.primary_engine == "Photon"
    assert route.secondary_engine == "FinancePlus"
    assert route.photon_doctype == "invoice"
    assert route.needs_cross_check is True


def test_low_confidence_invoice_requires_review():
    route = decide_route("Fattura", 0.65, photon_configured=True)
    assert route.needs_human_review is True
    assert route.needs_cross_check is True


def test_photon_budget_fallback():
    route = decide_route("Fattura", 0.99, photon_configured=True, photon_budget_remaining=0)
    assert route.primary_engine == "FinancePlus"
    assert any("Budget Photon" in warning for warning in route.warnings)


def test_invoice_quality_gate_happy_path():
    ok, issues = invoice_quality_gate(
        {
            "Total": 1137.14,
            "Subtotal": 932.08,
            "Tax": 205.06,
            "Shipping": 0,
            "Discount": 0,
            "Line_Items": [{"Amount": 932.08}],
            "Date": "2026-02-04",
        },
        "FATTURA nr. 1 del 04/02/2026",
    )
    assert ok is True
    assert issues == []


def test_invoice_quality_gate_detects_live_test_errors():
    ok, issues = invoice_quality_gate(
        {
            "Total": 1137.14,
            "Subtotal": 727.02,
            "Tax": 410.12,
            "Shipping": 0,
            "Discount": 0,
            "Line_Items": [{"Amount": 932.08}],
            "Date": "2026-04-02",
        },
        "FATTURA nr. FPR 1/26 del 04/02/2026",
    )
    assert ok is False
    assert any("Quadratura" in issue for issue in issues)
    assert any("Somma righe" in issue for issue in issues)
    assert any("inversione giorno/mese" in issue for issue in issues)
