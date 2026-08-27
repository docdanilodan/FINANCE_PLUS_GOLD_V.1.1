from __future__ import annotations
from dataclasses import dataclass, asdict
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
    cfads: Optional[float] = None
    debt_service: Optional[float] = None

@dataclass
class AnalyticsResult:
    metrics: dict
    data_quality: int
    score: Optional[int]
    rating: str
    semaphore: str
    warnings: list[str]

def div(a, b):
    return None if a is None or b in (None, 0) else a / b

def rating_for(score: int) -> str:
    for floor, label in [(97,'AAA'),(92,'AA'),(80,'A'),(60,'BBB'),(50,'BB'),(35,'B'),(20,'CCC'),(0,'D')]:
        if score >= floor: return label
    return 'D'

def analyze(i: FinancialInputs) -> AnalyticsResult:
    vals = asdict(i); present = sum(v is not None for v in vals.values())
    quality = round(100 * present / len(vals))
    pfn = None if i.financial_debt is None or i.cash is None else i.financial_debt - i.cash
    metrics = {
        'ebitda_margin': div(i.ebitda, i.revenue),
        'pfn': pfn,
        'pfn_ebitda': div(pfn, i.ebitda),
        'debt_equity': div(i.financial_debt, i.equity),
        'current_ratio': div(i.current_assets, i.current_liabilities),
        'dscr': div(i.cfads, i.debt_service),
    }
    warnings=[]
    if metrics['pfn_ebitda'] is None: warnings.append('PFN/EBITDA non calcolabile con i dati disponibili.')
    if metrics['dscr'] is None: warnings.append('DSCR non calcolabile senza CFADS e servizio del debito coerenti.')
    if quality < 60:
        return AnalyticsResult(metrics, quality, None, 'INCOMPLETO', 'INCOMPLETO', warnings + ['Qualita dati insufficiente per produrre un rating.'])
    score=50
    em=metrics['ebitda_margin']; pe=metrics['pfn_ebitda']; cr=metrics['current_ratio']; dscr=metrics['dscr']
    if em is not None: score += 15 if em >= .15 else 8 if em >= .08 else -5
    if pe is not None: score += 15 if pe <= 2 else 8 if pe <= 3.5 else -10
    if cr is not None: score += 10 if cr >= 1.3 else 4 if cr >= 1 else -7
    if dscr is not None: score += 10 if dscr >= 1.3 else 4 if dscr >= 1.1 else -10
    score=max(0,min(100,score)); rating=rating_for(score)
    sem='VERDE' if score >= 80 else 'GIALLO' if score >= 60 else 'ROSSO'
    return AnalyticsResult(metrics, quality, score, rating, sem, warnings)
