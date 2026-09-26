from financeplus.engines.business_plan import BusinessPlanAssumptions, project_business_plan

def test_bp_debt_declines_and_dscr_defined():
    a=BusinessPlanAssumptions(1_000_000,.05,.20,.24,50_000,.10,loan_amount=300_000,annual_interest_rate=.06,loan_years=5,depreciation_years=5)
    rows=project_business_plan(a,5)
    assert len(rows)==5
    assert rows[-1]["ending_debt"] <= rows[0]["ending_debt"]
    assert all(r["dscr"] is not None for r in rows)
