from analytics_engine import FinancialInputs, analyze
from document_ai import classify_text

def test_rating_gate():
    assert analyze(FinancialInputs()).rating == 'INCOMPLETO'

def test_document_priority():
    r=classify_text("Ricevuta dell'avvenuta presentazione via telematica deposito bilancio Camera di Commercio diritti di segreteria")
    assert r.category == "Ricevuta deposito Bilancio d'esercizio"
