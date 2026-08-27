from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Optional

@dataclass
class CRMonth:
    month: str
    granted: float = 0.0
    used: float = 0.0
    past_due: float = 0.0
    bad_debt: float = 0.0


def analyze_cr(months: Iterable[CRMonth]) -> dict:
    rows = list(months)
    if not rows:
        return {"status": "INCOMPLETO", "warnings": ["Nessun mese CR disponibile."]}
    last = rows[-1]
    util = None if last.granted <= 0 else last.used / last.granted
    max_past_due = max((r.past_due for r in rows), default=0.0)
    bad_debt = max((r.bad_debt for r in rows), default=0.0)
    warnings = []
    if util is not None and util > .90: warnings.append("Utilizzo affidamenti superiore al 90% nell'ultimo mese.")
    if max_past_due > 0: warnings.append("Presenza di scaduto/sconfinamento nel periodo analizzato.")
    if bad_debt > 0: warnings.append("Presenza di sofferenze: richiede verifica specialistica.")
    return {
        "status": "OK",
        "months": len(rows),
        "last_month": last.month,
        "granted_last": last.granted,
        "used_last": last.used,
        "utilization_last": util,
        "max_past_due": max_past_due,
        "bad_debt": bad_debt,
        "warnings": warnings,
    }
