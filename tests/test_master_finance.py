from financeplus.engines.finance import FinancialInputs, analyze_financials, maximum_financeable, compute_phantom, evaluate_mcc

def test_quality_gate_blocks_sparse_rating():
    r=analyze_financials(FinancialInputs(revenue=1000,ebitda=100))
    assert r.score is None and r.rating=="INCOMPLETO"

def test_financeable_is_monotonic_in_cfads():
    a=maximum_financeable(100000)["amount"]; b=maximum_financeable(200000)["amount"]
    assert b>a>0

def test_phantom_refuses_to_invent_weights():
    r=compute_phantom({"financial":80})
    assert r.score is None and r.status=="RICHIEDE_SORGENTE_ORIGINALE"

def test_mcc_refuses_without_ruleset():
    assert evaluate_mcc({}).status=="RICHIEDE_RULESET"
