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
