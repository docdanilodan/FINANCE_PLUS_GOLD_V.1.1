from analytics_engine import FinancialInputs, analyze
from document_ai import classify_text
from modules.mandate import MandateInputs, calculate_mandate


def test_rating_gate():
    assert analyze(FinancialInputs()).rating == "INCOMPLETO"


def test_document_priority():
    r = classify_text(
        "Ricevuta dell'avvenuta presentazione via telematica deposito bilancio "
        "Camera di Commercio diritti di segreteria"
    )
    assert r.category == "Ricevuta deposito Bilancio d'esercizio"


def test_detailed_financeplus_categories():
    assert classify_text("bozza di bilancio 2025 stato patrimoniale conto economico").category == "Bozza bilancio"
    assert classify_text("bilancio analitico al 31.12.2025 situazione contabile").category == "Bilancio analitico"
    assert classify_text("prospetto di bilancio riclassificato comparato").category == "Prospetto bilancio"
    assert classify_text("company profile presentazione aziendale pitch deck").category == "Presentazione aziendale"
    assert classify_text("centrale rischi banca d'italia accordato utilizzato").category == "Centrale Rischi Banca d'Italia"


def test_receipt_uses_balance_year_not_protocol_year():
    r = classify_text(
        "Ricevuta dell'avvenuta presentazione via telematica deposito bilancio. "
        "Data atto 31/12/2023. Protocollo del 22/02/2025. Diritti di segreteria."
    )
    assert r.category == "Ricevuta deposito Bilancio d'esercizio"
    assert r.document_year == 2023


def test_central_risk_period_and_reference_date():
    r = classify_text(
        "Centrale Rischi Banca d'Italia - mese di riferimento luglio 2026 - accordato utilizzato"
    )
    assert r.category == "Centrale Rischi Banca d'Italia"
    assert r.document_year == 2026
    assert r.period == "luglio 2026"
    assert r.reference_date == "2026-07-31"


def test_bank_statement_metadata():
    r = classify_text(
        "Estratto conto Intesa Sanpaolo IBAN saldo movimenti dal 01/04/2026 al 30/06/2026"
    )
    assert r.category == "Estratto conto"
    assert r.bank == "Intesa Sanpaolo"
    assert r.document_year == 2026
    assert r.period == "2° trimestre"
    assert r.reference_date == "2026-06-30"


def test_visura_reference_date():
    r = classify_text(
        "Camera di Commercio Registro Imprese Visura ordinaria - data estrazione 24/08/2026"
    )
    assert r.category == "Visura Camerale"
    assert r.reference_date == "2026-08-24"


def test_mandate_calculation_is_deterministic():
    result = calculate_mandate(
        MandateInputs(
            requested_amount=120000,
            approved_amount=100000,
            fee_pct=0.02,
            fixed_fee=500,
            vat_pct=0.22,
            withholding_pct=0,
        )
    )
    assert result["fee_base"] == 100000
    assert result["variable_fee"] == 2000
    assert result["taxable_fee"] == 2500
    assert result["vat"] == 550
    assert result["total_due"] == 3050
