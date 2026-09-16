from __future__ import annotations
from dataclasses import dataclass, asdict
from math import isfinite
from typing import Optional

@dataclass
class FinancialInputs:
    revenue: Optional[float] = None
    ebitda: Optional[float] = None
    ebit: Optional[float] = None
    financial_debt: Optional[float] = None
    cash: Optional[float] = None
    equity: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    total_assets: Optional[float] = None
    cfads: Optional[float] = None
    debt_service: Optional[float] = None
    interest_expense: Optional[float] = None
    cfo: Optional[float] = None

@dataclass
class FinancialResult:
    metrics: dict[str, float | None]
    data_quality: int
    score: int | None
    rating: str
    semaphore: str
    warnings: list[str]


def _valid(v):
    return v is not None and isinstance(v, (int, float)) and isfinite(float(v))

def _div(a, b):
    return None if not _valid(a) or not _valid(b) or float(b) == 0 else float(a) / float(b)

def rating_for(score: int) -> str:
    for floor, label in [(97, "AAA"), (92, "AA"), (80, "A"), (60, "BBB"), (50, "BB"), (35, "B"), (20, "CCC"), (0, "D")]:
        if score >= floor: return label
    return "D"

def analyze_financials(i: FinancialInputs, *, minimum_quality: int = 60) -> FinancialResult:
    vals = asdict(i)
    present = sum(_valid(v) for v in vals.values())
    quality = round(100 * present / len(vals))
    pfn = None if not _valid(i.financial_debt) or not _valid(i.cash) else float(i.financial_debt) - float(i.cash)
    metrics = {
        "ebitda_margin": _div(i.ebitda, i.revenue),
        "pfn": pfn,
        "pfn_ebitda": _div(pfn, i.ebitda),
        "debt_equity": _div(i.financial_debt, i.equity),
        "current_ratio": _div(i.current_assets, i.current_liabilities),
        "dscr": _div(i.cfads, i.debt_service),
        "interest_coverage": _div(i.ebit, i.interest_expense),
        "equity_ratio": _div(i.equity, i.total_assets),
        "cfo_debt": _div(i.cfo, i.financial_debt),
    }
    warnings: list[str] = []
    if metrics["pfn_ebitda"] is None: warnings.append("PFN/EBITDA non calcolabile con dati disponibili.")
    if metrics["dscr"] is None: warnings.append("DSCR non calcolabile senza CFADS e debt service coerenti.")
    if quality < minimum_quality:
        return FinancialResult(metrics, quality, None, "INCOMPLETO", "INCOMPLETO", warnings + ["Data Quality Gate: qualità insufficiente per rating."])
    score = 50
    em, pe, cr, dscr, ic = metrics["ebitda_margin"], metrics["pfn_ebitda"], metrics["current_ratio"], metrics["dscr"], metrics["interest_coverage"]
    if em is not None: score += 15 if em >= .15 else 8 if em >= .08 else -5
    if pe is not None: score += 15 if pe <= 2 else 8 if pe <= 3.5 else -10
    if cr is not None: score += 10 if cr >= 1.3 else 4 if cr >= 1 else -7
    if dscr is not None: score += 10 if dscr >= 1.3 else 4 if dscr >= 1.1 else -10
    if ic is not None: score += 5 if ic >= 3 else 2 if ic >= 1.5 else -5
    score = max(0, min(100, int(round(score))))
    return FinancialResult(metrics, quality, score, rating_for(score), "VERDE" if score >= 80 else "GIALLO" if score >= 60 else "ROSSO", warnings)

def _annual_payment_per_euro(rate: float, years: int) -> float:
    if years <= 0: raise ValueError("years must be > 0")
    r = max(0.0, float(rate))
    if r == 0: return 1.0 / years
    return r / (1 - (1 + r) ** (-years))

def maximum_financeable(cfads: float, *, target_dscr: float = 1.25, annual_rate: float = 0.06, years: int = 5, haircut: float = 0.90) -> dict:
    if cfads <= 0 or target_dscr <= 0: return {"status": "INCOMPLETO", "amount": None, "warning": "CFADS e target DSCR devono essere positivi."}
    max_debt_service = cfads / target_dscr
    payment_per_euro = _annual_payment_per_euro(annual_rate, years)
    amount = max_debt_service / payment_per_euro * max(0.0, min(1.0, haircut))
    return {"status": "OK", "amount": amount, "max_annual_debt_service": max_debt_service, "target_dscr": target_dscr, "annual_rate": annual_rate, "years": years, "haircut": haircut, "method": "DSCR-constrained annuity sizing"}
