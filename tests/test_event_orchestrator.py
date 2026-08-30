from services.event_orchestrator import FinancePlusEventOrchestrator


def test_document_sensitivity_high_risk():
    assert FinancePlusEventOrchestrator._document_sensitivity("Centrale Rischi") == "Altamente riservato"
    assert FinancePlusEventOrchestrator._document_sensitivity("Estratto conto") == "Altamente riservato"
    assert FinancePlusEventOrchestrator._document_sensitivity("Documento identità") == "Altamente riservato"


def test_document_sensitivity_confidential():
    assert FinancePlusEventOrchestrator._document_sensitivity("Bilancio") == "Riservato"
    assert FinancePlusEventOrchestrator._document_sensitivity("Contratto") == "Riservato"


def test_document_sensitivity_internal_default():
    assert FinancePlusEventOrchestrator._document_sensitivity("Visura camerale") == "Interno"
    assert FinancePlusEventOrchestrator._document_sensitivity("Altro") == "Interno"
