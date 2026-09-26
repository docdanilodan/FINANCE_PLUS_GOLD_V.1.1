from __future__ import annotations
import io, json, re, zipfile
from pathlib import Path
from typing import Any
import pandas as pd

DATE_KEYS = ("data", "date", "valuta", "booking")
DESC_KEYS = ("descrizione", "description", "causale", "details", "memo", "payee")
AMOUNT_KEYS = ("importo", "amount", "movimento", "value")
CREDIT_KEYS = ("accredito", "entrate", "credit", "dare")
DEBIT_KEYS = ("addebito", "uscite", "debit", "avere")

def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "").replace("\x00", " ")).strip()

def _amount(v: Any) -> float | None:
    if v is None: return None
    if isinstance(v, (int, float)): return float(v)
    s = re.sub(r"[^0-9,().+\-]", "", str(v)).replace("(", "-").replace(")", "")
    if not s: return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s: s = s.replace(".", "").replace(",", ".")
    try: return float(s)
    except Exception: return None

def _text_transactions(text: str) -> pd.DataFrame:
    rows=[]
    dpat=re.compile(r"\b(\d{1,2}[./-]\d{1,2}[./-](?:\d{2}|\d{4}))\b")
    apat=re.compile(r"(?<!\d)([-+]?\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})|[-+]?\s*\d+(?:[.,]\d{2}))(?!\d)")
    for line in text.splitlines():
        dm=dpat.search(line); am=apat.findall(line)
        if not dm or not am: continue
        val=_amount(am[-1])
        if val is None: continue
        desc=line.replace(dm.group(0), " ")
        for a in am: desc=desc.replace(a, " ")
        rows.append({"date":dm.group(1),"description":_clean(desc),"amount":val})
    return pd.DataFrame(rows)


def _pdf_statement_transactions(pdf) -> pd.DataFrame:
    """Parse textual bank-statement PDFs using PDF word coordinates.

    Supports common Italian layouts such as DARE/AVERE, MOVIMENTI DARE/AVERE,
    and USCITE/ENTRATE. Coordinates determine the debit/credit sign.
    """
    rows: list[dict[str, Any]] = []
    money_re = re.compile(r"^-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})$")
    one_date = re.compile(r"^\d{1,2}[./-]\d{1,2}(?:[./-](?:\d{2}|\d{4}))?$")

    def group_lines(words: list[dict], tol: float = 1.8):
        out: list[list[dict]] = []
        for w in sorted(words, key=lambda z: (z["top"], z["x0"])):
            if not out or abs(w["top"] - out[-1][0]["top"]) > tol:
                out.append([w])
            else:
                out[-1].append(w)
        return [sorted(line, key=lambda z: z["x0"]) for line in out]

    def consume_date(tokens: list[str], pos: int) -> tuple[str | None, int]:
        if pos >= len(tokens): return None, pos
        t = tokens[pos]
        if one_date.match(t): return t, pos + 1
        if pos + 2 < len(tokens) and all(re.fullmatch(r"\d{1,2}", tokens[pos+i]) for i in range(3)):
            dd, mm, yy = tokens[pos:pos+3]
            if 1 <= int(dd) <= 31 and 1 <= int(mm) <= 12:
                return f"{int(dd):02d}/{int(mm):02d}/{yy}", pos + 3
        return None, pos

    for page in pdf.pages:
        debit_x = credit_x = None
        words = page.extract_words(x_tolerance=2, y_tolerance=2) or []
        for line in group_lines(words):
            tokens = [w["text"] for w in line]
            upper = [t.upper() for t in tokens]
            if "DARE" in upper and "AVERE" in upper:
                debit_x = next(w["x0"] for w,t in zip(line, upper) if t == "DARE")
                credit_x = next(w["x0"] for w,t in zip(line, upper) if t == "AVERE")
                continue
            if "USCITE" in upper and "ENTRATE" in upper:
                debit_x = next(w["x0"] for w,t in zip(line, upper) if t == "USCITE")
                credit_x = next(w["x0"] for w,t in zip(line, upper) if t == "ENTRATE")
                continue
            if debit_x is None or credit_x is None: continue
            date1, pos = consume_date(tokens, 0)
            if date1 is None: continue
            date2, pos2 = consume_date(tokens, pos)
            chosen_date = date2 or date1
            if not chosen_date or not re.search(r"(?:\d{2}|\d{4})$", chosen_date): continue
            money_candidates=[]
            for idx,w in enumerate(line):
                if idx < pos2: continue
                if money_re.match(w["text"]):
                    center=(w["x0"]+w["x1"])/2.0
                    d_dist=abs(center-debit_x); c_dist=abs(center-credit_x)
                    if min(d_dist,c_dist) <= max(75.0, abs(credit_x-debit_x)*0.8):
                        money_candidates.append((min(d_dist,c_dist),d_dist,c_dist,idx,w))
            if not money_candidates: continue
            _, d_dist, c_dist, amount_idx, aw = min(money_candidates, key=lambda x:x[0])
            value=_amount(aw["text"])
            if value is None: continue
            amount = -abs(float(value)) if d_dist <= c_dist else abs(float(value))
            desc_tokens=[w["text"] for i,w in enumerate(line) if i >= pos2 and i != amount_idx]
            desc=_clean(" ".join(desc_tokens)); udesc=desc.upper()
            if "SALDO INIZIALE" in udesc or "SALDO FINALE" in udesc or "SALDO COME DA COMUNICAZIONE" in udesc: continue
            rows.append({"date": chosen_date, "description": desc, "amount": amount})
    return pd.DataFrame(rows)

def parse_statement(name: str, data: bytes) -> pd.DataFrame:
    ext=Path(name).suffix.lower()
    if ext==".csv":
        for enc in ("utf-8-sig","utf-8","cp1252","latin1"):
            try:return pd.read_csv(io.BytesIO(data),sep=None,engine="python",encoding=enc)
            except Exception: pass
        raise ValueError("CSV non leggibile")
    if ext in (".xlsx",".xls"):
        sheets=pd.read_excel(io.BytesIO(data),sheet_name=None)
        return pd.concat([x for x in sheets.values() if not x.empty],ignore_index=True) if sheets else pd.DataFrame()
    if ext in (".txt",".sta",".ofx",".qif",".xml"):
        return _text_transactions(data.decode("utf-8",errors="ignore"))
    if ext==".json": return pd.json_normalize(json.loads(data.decode("utf-8-sig")))
    if ext==".docx":
        from docx import Document
        doc=Document(io.BytesIO(data)); return _text_transactions("\n".join(p.text for p in doc.paragraphs))
    if ext==".pdf":
        try: import pdfplumber
        except Exception as exc: raise RuntimeError("pdfplumber richiesto per PDF E/C") from exc
        text=[]; tables=[]
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            layout_tx = _pdf_statement_transactions(pdf)
            if not layout_tx.empty: return layout_tx
            for page in pdf.pages:
                text.append(page.extract_text() or "")
                for t in page.extract_tables() or []:
                    if not t or len(t)<=1: continue
                    width=len(t[0]); hdr=[_clean(x) or f"col_{i+1}" for i,x in enumerate(t[0])]
                    header=" ".join(hdr).lower()
                    if not (any(k in header for k in DATE_KEYS) and (any(k in header for k in AMOUNT_KEYS+CREDIT_KEYS+DEBIT_KEYS))): continue
                    tables.append(pd.DataFrame([(r+[""]*width)[:width] for r in t[1:]],columns=hdr))
        return pd.concat(tables,ignore_index=True) if tables else _text_transactions("\n".join(text))
    if ext==".zip":
        frames=[]
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for info in z.infolist():
                if info.is_dir(): continue
                try: frames.append(parse_statement(info.filename,z.read(info)))
                except Exception: continue
        return pd.concat([f for f in frames if not f.empty],ignore_index=True) if frames else pd.DataFrame()
    raise ValueError(f"Formato E/C non supportato: {ext or '(senza estensione)'}")

def normalize_transactions(raw: pd.DataFrame) -> pd.DataFrame:
    if raw is None or raw.empty: return pd.DataFrame(columns=["date","description","amount"])
    x=raw.copy(); x.columns=[_clean(c).lower() for c in x.columns]
    def pick(keys): return next((c for c in x.columns if any(k in c for k in keys)),None)
    dc=pick(DATE_KEYS); desc=pick(DESC_KEYS); ac=pick(AMOUNT_KEYS); cc=pick(CREDIT_KEYS); db=pick(DEBIT_KEYS)
    if not dc: raise ValueError("Colonna data non identificata")
    out=pd.DataFrame(); out["date"]=pd.to_datetime(x[dc],errors="coerce",dayfirst=True)
    out["description"]=x[desc].map(_clean) if desc else ""
    if ac: out["amount"]=x[ac].map(_amount)
    elif cc or db:
        cred=x[cc].map(_amount) if cc else pd.Series([0.0]*len(x),index=x.index)
        deb=x[db].map(_amount) if db else pd.Series([0.0]*len(x),index=x.index)
        out["amount"]=cred.fillna(0.0)-deb.fillna(0.0).abs()
    else: raise ValueError("Colonna importo non identificata")
    out["amount"]=pd.to_numeric(out["amount"],errors="coerce")
    return out.dropna(subset=["date","amount"]).sort_values("date").reset_index(drop=True)

def analyze_cashflow(tx: pd.DataFrame, *, opening_balance: float | None = None) -> dict:
    x=normalize_transactions(tx) if not set(("date","amount")).issubset(tx.columns) else tx.copy()
    x["date"]=pd.to_datetime(x["date"],errors="coerce"); x["amount"]=pd.to_numeric(x["amount"],errors="coerce"); x=x.dropna(subset=["date","amount"]).sort_values("date")
    if x.empty:return {"status":"INCOMPLETO","warnings":["Nessun movimento valido."]}
    inflows=float(x.loc[x.amount>0,"amount"].sum()); outflows=float(-x.loc[x.amount<0,"amount"].sum()); net=inflows-outflows
    monthly=x.assign(month=x.date.dt.to_period("M").astype(str)).groupby("month")["amount"].sum()
    result={"status":"OK","transactions":int(len(x)),"from":str(x.date.min().date()),"to":str(x.date.max().date()),"inflows":inflows,"outflows":outflows,"net_cashflow":net,"avg_monthly_net":float(monthly.mean()),"negative_months":int((monthly<0).sum()),"warnings":[]}
    if opening_balance is not None:
        bal=float(opening_balance)+x.groupby(x.date.dt.date)["amount"].sum().cumsum()
        result.update({"closing_balance":float(bal.iloc[-1]),"average_daily_balance":float(bal.mean()),"negative_days":int((bal<0).sum()),"minimum_balance":float(bal.min())})
    return result
