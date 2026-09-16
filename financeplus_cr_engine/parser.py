from __future__ import annotations
import re
from pathlib import Path
from .models import ParsedCR, CRRow, Guarantee, InfoRequest, Correction

MONTHS={"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,"luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12,
        "gen":1,"feb":2,"mar":3,"apr":4,"mag":5,"giu":6,"lug":7,"ago":8,"set":9,"ott":10,"nov":11,"dic":12}
NUM_RE=re.compile(r"^-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?$")

def _money(s: str) -> float:
    s=s.strip().replace("€","").replace(" ","")
    if "," in s:s=s.replace(".","").replace(",",".")
    else:
        parts=s.split(".")
        if len(parts)>1 and all(len(p)==3 for p in parts[1:]):s="".join(parts)
    try:return float(s)
    except Exception:return 0.0

def _period_full(text: str) -> str | None:
    m=re.search(r"\b("+"|".join(k for k in MONTHS if len(k)>3)+r")\s+(20\d{2}|19\d{2})\b",text,re.I)
    if not m:return None
    mo=MONTHS[m.group(1).lower()]; y=int(m.group(2)); return f"{mo:02d}/{y}"

def _requested_periods(text: str) -> list[str]:
    found=[]
    for mon,yy in re.findall(r"\b(gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic)-(\d{2})\b",text.lower()):found.append(f"{MONTHS[mon]:02d}/{2000+int(yy)}")
    return sorted(set(found),key=lambda z:(int(z[3:]),int(z[:2])))

def _category(text: str, section: str) -> str:
    u=" ".join(text.upper().replace(".","").split())
    if "SOFFERENZ" in u:return "sofferenze"
    if "AUTOLIQUID" in u:return "autoliquidanti"
    if "RISCHI A REVOCA" in u:return "a revoca"
    if "RISCHI A SCAD" in u:return "a scadenza"
    if "CREDITI DI FIRMA" in u or section=="crediti di firma":return "crediti di firma"
    if "GARANZIE RICEVUTE" in u or section=="garanzie ricevute":return "garanzie"
    if "FACTORING" in u:return "factoring"
    if "LEASING" in u:return "leasing"
    return "non classificata"

def _cluster_lines(words: list[dict], tol: float=1.15):
    lines=[]
    for w in sorted(words,key=lambda z:(z["top"],z["x0"])):
        if not lines or abs(w["top"]-lines[-1][0])>tol:lines.append([w["top"],[w]])
        else:lines[-1][1].append(w)
    return [(top,sorted(ws,key=lambda z:z["x0"])) for top,ws in lines]

def extract_text(path):
    path=Path(path); ext=path.suffix.lower(); warnings=[]
    if ext==".pdf":
        from pypdf import PdfReader
        pages=[]
        for i,p in enumerate(PdfReader(str(path)).pages,1):
            try:pages.append(f"\n[[PAGE {i}]]\n"+(p.extract_text() or ""))
            except Exception as exc:warnings.append(f"Pagina {i} non leggibile: {exc}")
        return "\n".join(pages),warnings
    if ext in (".txt",".csv",".json",".xml",".md"):return path.read_text(encoding="utf-8",errors="ignore"),warnings
    if ext in (".xlsx",".xls"):
        import pandas as pd
        xl=pd.ExcelFile(path); return "\n".join(pd.read_excel(path,sheet_name=s,header=None).to_csv(index=False,header=False) for s in xl.sheet_names),warnings
    raise ValueError(f"Formato non interpretabile: {ext}")

def _parse_bdi_pdf(path: Path) -> ParsedCR:
    import pdfplumber
    result=ParsedCR(source_name=path.name)
    seen=set(); requested=[]; current_period=""; current_bank=""; section=""; correction_history=False
    with pdfplumber.open(str(path)) as pdf:
        if not pdf.pages:return result
        first=pdf.pages[0].extract_text() or ""; requested=_requested_periods(first); result.periods=requested.copy()
        m=re.search(r"^\s*Intestatario:\s*(.+?)\s*$",first,re.I|re.M)
        if m:result.subject=" ".join(m.group(1).split())[:100]
        m=re.search(r"Codice fiscale:\s*([A-Z0-9]{11,20})",first,re.I)
        if m:result.tax_code=m.group(1)
        allowed=set(requested)
        for pno,page in enumerate(pdf.pages,1):
            page_text=page.extract_text() or ""
            if re.search(r"Il prospetto dati della Centrale dei rischi:\s*guida alla lettura",page_text,re.I|re.S):break
            lines=_cluster_lines(page.extract_words(x_tolerance=1.5,y_tolerance=2) or []); texts=[" ".join(w["text"] for w in ws) for _,ws in lines]
            for i,(top,ws) in enumerate(lines):
                text=texts[i]; u=text.upper(); near=" ".join(texts[max(0,i-1):min(len(texts),i+2)])
                if "DATA DI RIFERIMENTO" in near.upper():
                    pp=_period_full(near)
                    if pp and (not allowed or pp in allowed):current_period=pp; correction_history=False
                if "INTERMEDIARIO:" in u:
                    m=re.search(r"Intermediario:\s*(.+)$",text,re.I)
                    if m and m.group(1).strip():current_bank=" ".join(m.group(1).split())[:160]
                    correction_history=False
                if "CREDITI PER CASSA" in u:section="crediti per cassa"
                elif "CREDITI DI FIRMA" in u:section="crediti di firma"
                elif "GARANZIE RICEVUTE" in u:section="garanzie ricevute"
                elif "DERIVATI" in u and "FINANZIARI" in u:section="derivati"
                if "PRIMA DELLE CORREZIONI" in near.upper():correction_history=True
                if "SITUAZIONE CORRENTE" in u:correction_history=False
                if correction_history or not current_period or (allowed and current_period not in allowed) or not current_bank:continue
                numeric=[w for w in ws if w["x0"]>page.width*0.58 and NUM_RE.match(w["text"])]; vals=[_money(w["text"]) for w in numeric]
                if len(vals)>=6:
                    vals=vals[-6:]; accorded,operating,used,guaranteed=vals[-5],vals[-4],vals[-3],vals[-1]
                elif len(vals)>=3 and section in ("crediti di firma","garanzie ricevute"):
                    vals=vals[-3:]; accorded,operating,used=vals[-3],vals[-2],vals[-1]; guaranteed=0.0
                else:continue
                window=" ".join(texts[max(0,i-9):min(len(texts),i+6)]); cat=_category(window,section); over=max(0.0,used-operating) if operating else 0.0
                key=(current_period,current_bank,cat,round(accorded,2),round(operating,2),round(used,2),round(guaranteed,2),pno)
                if key in seen:continue
                seen.add(key); result.rows.append(CRRow(period=current_period,intermediary=current_bank,category=cat,technical_form=cat,accorded=accorded,operating_accorded=operating,used=used,guaranteed=guaranteed,overrun=over,source_page=pno,raw=text[:500]))
                low=window.lower()
                if "cointestazione" in low or "garante" in low or "fondo di garanzia" in low:result.guarantees.append(Guarantee(current_period,current_bank,window[:150],guaranteed,guaranteed,"cointestazione" in low,pno))
            for line in page_text.splitlines():
                low=line.lower()
                if "prima informazione" in low and current_bank:result.info_requests.append(InfoRequest(current_bank,requested_period=current_period,reason=" ".join(line.split())[:160],source_page=pno))
                if "rettifica" in low and current_bank:result.corrections.append(Correction(current_period,current_bank," ".join(line.split())[:180],pno))
    row_periods=sorted({r.period for r in result.rows},key=lambda z:(int(z[3:]),int(z[:2])))
    if requested and not row_periods:result.warnings.append("Periodi richiesti rilevati ma nessuna riga quantitativa riclassificata.")
    elif requested and len(row_periods)<min(6,len(requested)):result.warnings.append(f"Copertura quantitativa parziale: {len(row_periods)} periodi con righe su {len(requested)} richiesti.")
    return result

def parse_file(path):
    p=Path(path)
    if p.suffix.lower()==".pdf":
        try:return _parse_bdi_pdf(p)
        except Exception as exc:
            text,warnings=extract_text(p); parsed=parse_text(text); parsed.source_name=p.name; parsed.warnings.extend([f"Parser BDI posizionale non riuscito: {exc}",*warnings]); return parsed
    text,warnings=extract_text(p); parsed=parse_text(text); parsed.source_name=p.name; parsed.warnings.extend(warnings); return parsed

def parse_text(text):
    result=ParsedCR(); norm=text.replace("\xa0"," "); result.periods=sorted(set(_requested_periods(norm)),key=lambda z:(int(z[3:]),int(z[:2])))
    m=re.search(r"(?:Intestatario|Denominazione)\s*[:\-]?\s*([^\n]{4,100})",norm,re.I)
    if m:result.subject=" ".join(m.group(1).split())[:100]
    m=re.search(r"(?:codice fiscale|c\.f\.|partita iva|p\.iva)\s*[:\-]?\s*([A-Z0-9]{11,20})",norm,re.I)
    if m:result.tax_code=m.group(1)
    result.warnings.append("Formato testuale acquisito: riclassificazione quantitativa richiede struttura CR riconoscibile.")
    return result
