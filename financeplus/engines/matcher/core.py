from __future__ import annotations
from financeplus.domain import OperatorProfile

def rank_operators(features: dict[str,float], operators: list[OperatorProfile], *, top_n: int = 20) -> list[dict]:
    """Explainable internal Fit ranking. No operator catalogue or weights are fabricated."""
    rows=[]
    for op in operators:
        if not op.active: continue
        weighted=0.0; denom=0.0; missing=[]
        for k,w in op.weights.items():
            if k not in features or features[k] is None: missing.append(k); continue
            value=max(0.0,min(100.0,float(features[k]))); weighted+=value*float(w); denom+=abs(float(w))
        fit=None if denom==0 else weighted/denom
        rows.append({"operator":op.name,"code":op.code,"category":op.category,"fit":None if fit is None else round(fit,2),"missing_features":missing,"required_documents":op.required_documents,"source":op.source,"method":"FinancePlus internal explainable fit; not official approval probability"})
    rows.sort(key=lambda r:(r["fit"] is not None, r["fit"] or -1), reverse=True)
    return rows[:max(1,top_n)]
