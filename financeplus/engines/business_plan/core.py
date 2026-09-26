from __future__ import annotations
from dataclasses import dataclass

@dataclass
class BusinessPlanAssumptions:
    base_revenue: float
    revenue_growth: float
    ebitda_margin: float
    tax_rate: float
    annual_capex: float
    nwc_pct_revenue: float
    loan_amount: float = 0.0
    annual_interest_rate: float = 0.06
    loan_years: int = 5
    depreciation_years: int = 5


def _payment(principal: float, rate: float, years: int) -> float:
    if principal <= 0: return 0.0
    if years <= 0: raise ValueError("loan_years must be > 0")
    if rate == 0: return principal / years
    return principal * rate / (1 - (1 + rate) ** (-years))

def project_business_plan(a: BusinessPlanAssumptions, years: int = 5) -> list[dict]:
    if years <= 0: raise ValueError("years must be > 0")
    revenue=float(a.base_revenue); prior_nwc=revenue*a.nwc_pct_revenue; debt=float(a.loan_amount)
    payment=_payment(debt,a.annual_interest_rate,a.loan_years) if debt>0 else 0.0
    depreciation=a.annual_capex/max(1,a.depreciation_years)
    out=[]
    for y in range(1,years+1):
        revenue*=1+a.revenue_growth
        ebitda=revenue*a.ebitda_margin
        nwc=revenue*a.nwc_pct_revenue; delta_nwc=nwc-prior_nwc; prior_nwc=nwc
        interest=debt*a.annual_interest_rate if debt>0 else 0.0
        principal=max(0.0,min(debt,payment-interest)) if payment>0 else 0.0
        debt_service=interest+principal
        taxable=max(0.0,ebitda-depreciation-interest)
        taxes=taxable*a.tax_rate
        cfads=ebitda-taxes-a.annual_capex-delta_nwc
        dscr=None if debt_service<=0 else cfads/debt_service
        debt=max(0.0,debt-principal)
        out.append({"year":y,"revenue":revenue,"ebitda":ebitda,"depreciation":depreciation,"interest":interest,"taxable_income":taxable,"taxes":taxes,"capex":a.annual_capex,"nwc":nwc,"delta_nwc":delta_nwc,"cfads":cfads,"principal":principal,"debt_service":debt_service,"ending_debt":debt,"dscr":dscr})
    return out
