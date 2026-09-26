import pandas as pd
from financeplus.engines.cashflow import normalize_transactions, analyze_cashflow

def test_cashflow_basic():
    raw=pd.DataFrame({"Data":["01/01/2026","02/01/2026","03/01/2026"],"Descrizione":["A","B","C"],"Importo":[1000,-250,-300]})
    tx=normalize_transactions(raw); r=analyze_cashflow(tx,opening_balance=0)
    assert r["status"]=="OK" and r["net_cashflow"]==450 and r["closing_balance"]==450
