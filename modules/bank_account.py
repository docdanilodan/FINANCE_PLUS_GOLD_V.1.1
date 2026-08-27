from __future__ import annotations
import pandas as pd

REQUIRED = {"date", "amount"}

def analyze_transactions(df: pd.DataFrame) -> dict:
    missing = REQUIRED - set(df.columns)
    if missing:
        return {"status": "INCOMPLETO", "warnings": [f"Colonne mancanti: {', '.join(sorted(missing))}"]}
    x = df.copy()
    x["date"] = pd.to_datetime(x["date"], errors="coerce")
    x["amount"] = pd.to_numeric(x["amount"], errors="coerce")
    x = x.dropna(subset=["date", "amount"]).sort_values("date")
    if x.empty:
        return {"status": "INCOMPLETO", "warnings": ["Nessun movimento valido."]}
    inflows = float(x.loc[x.amount > 0, "amount"].sum())
    outflows = float(-x.loc[x.amount < 0, "amount"].sum())
    net = inflows - outflows
    monthly = x.assign(month=x.date.dt.to_period("M").astype(str)).groupby("month")["amount"].sum()
    return {
        "status": "OK", "transactions": int(len(x)), "from": str(x.date.min().date()), "to": str(x.date.max().date()),
        "inflows": inflows, "outflows": outflows, "net_cashflow": net,
        "avg_monthly_net": float(monthly.mean()), "negative_months": int((monthly < 0).sum()),
        "warnings": [],
    }
