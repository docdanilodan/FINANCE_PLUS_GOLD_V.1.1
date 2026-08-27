from __future__ import annotations
from dataclasses import dataclass

@dataclass
class BPInputs:
    base_revenue: float
    revenue_growth: float
    ebitda_margin: float
    tax_rate: float = .24
    capex: float = 0.0
    working_capital_pct: float = .10


def project(i: BPInputs, years: int = 5) -> list[dict]:
    out=[]; revenue=i.base_revenue
    for y in range(1, years+1):
        revenue *= 1 + i.revenue_growth
        ebitda = revenue * i.ebitda_margin
        taxes = max(0.0, ebitda * i.tax_rate)
        wc = revenue * i.working_capital_pct
        out.append({"year": y, "revenue": revenue, "ebitda": ebitda, "taxes_proxy": taxes, "working_capital_proxy": wc})
    return out
