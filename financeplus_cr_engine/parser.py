from __future__ import annotations
import re
from pathlib import Path
from typing import List, Tuple
from .models import ParsedCR, CRRow, Guarantee, InfoRequest, Correction
MONTHS={"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,"luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12,"gen":1,"feb":2,"mar":3,"apr":4,"mag":5,"giu":6,"lug":7,"ago":8,"set":9,"ott":10,"nov":11,"dic":12}
BANK_TOKENS=("BANCA ","BANCO ","B.C.C.","BCC ","CREDITO COOPERATIVO","S.P.A."," SPA","FACTORING","LEASING","FINANZIARIA","MEDIOCREDITO","CONFIDI","SGR","INTERMEDIARIO")
BLACKLIST=("NUMERO VERDE","BANCA D'ITALIA","BANCA D’ITALIA","SERVIZI INFORMATIVI","WWW.","PAGINA ","CENTRALE DEI RISCHI","AVVERTENZE","ISTRUZIONI","CHIAMANDO","CONSULENZA","INFORMATIVA","LE INFORMAZIONI PRESENTI","CODICE QR")
CATEGORY_MAP={"rischi autoliquidanti":"autoliquidanti","rischi a scadenza":"a scadenza","rischi a revoca":"a revoca","sofferenze":"sofferenze","garanzie ricevute":"garanzie","crediti di firma":"crediti di firma","derivati":"derivati","factoring":"factoring","leasing":"leasing"}
AMOUNT_RE=re.compile(r"(?<!\w)(?:€\s*)?([+-]?(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:,\d{1,2})?)")
def _money(s):
    s=s.strip().replace("€","").replace(" ","")
    if "," in s:s=s.replace(".","").replace(",",".")
    else:
        parts=s.split(".")
        if len(parts)>1 and all(len(p)==3 for p in parts[1:]):s="".join(parts)
    try:return float(s)
    except:return 0.0
def _periods(text):
    out=[]
    for m in re.finditer(r"\b("+"|".join(MONTHS)+r")\s+(20\d{2}|19\d{2})\b",text,re.I):
        mo=MONTHS[m.group(1).lower()];y=int(m.group(2));out.append((m.start(),y*100+mo,f"{mo:02d}/{y}"))
    for m in re.finditer(r"\b(0?[1-9]|1[0-2])[/-](20\d{2}|19\d{2})\b",text):
        mo=int(m.group(1));y=int(m.group(2));out.append((m.start(),y*100+mo,f"{mo:02d}/{y}"))
    return sorted(out)
def _valid_intermediary(line):
    u=" ".join(line.upper().split());return 5<=len(u)<=180 and not any(x in u for x in BLACKLIST) and any(tok in u for tok in BANK_TOKENS)
def _clean_bank(line):return re.sub(r"\s+(?:€|\d).*$","",re.sub(r"\s+"," ",line).strip(" -:;\t")).strip()[:160]
def extract_text(path):
    path=Path(path);ext=path.suffix.lower();warnings=[]
    if ext=='.pdf':
        from pypdf import PdfReader
        pages=[]
        for i,p in enumerate(PdfReader(str(path)).pages,1):
            try:pages.append(f"\n[[PAGE {i}]]\n"+(p.extract_text() or ""))
            except Exception as e:warnings.append(f"Pagina {i} non leggibile: {e}")
        return "\n".join(pages),warnings
    if ext in ('.txt','.csv','.json','.xml','.md'):return path.read_text(encoding='utf-8',errors='ignore'),warnings
    if ext in ('.xlsx','.xls'):
        import pandas as pd
        xl=pd.ExcelFile(path);return "\n".join(pd.read_excel(path,sheet_name=s,header=None).to_csv(index=False,header=False) for s in xl.sheet_names),warnings
    raise ValueError(f"Formato non interpretabile: {ext}")
def parse_file(path):
    p=Path(path);text,warnings=extract_text(p);parsed=parse_text(text);parsed.source_name=p.name;parsed.warnings.extend(warnings);return parsed
def parse_text(text):
    result=ParsedCR();norm=text.replace('\xa0',' ');lines=[re.sub(r"\s+"," ",x).strip() for x in norm.splitlines()]
    for pat in (r"(?:soggetto della visura|intestatario|denominazione)\s*[:\-]?\s*([A-Z0-9 '&.\-]{4,100})",r"ANALISI\s+CR\s+AVANZATA\s+([A-Z0-9 '&.\-]{4,100})"):
        m=re.search(pat,norm,re.I|re.S)
        if m:
            cand=" ".join(m.group(1).splitlines()[0].split())
            if not any(x in cand.upper() for x in BLACKLIST):result.subject=cand[:100];break
    cf=re.search(r"(?:codice fiscale|c\.f\.|partita iva|p\.iva)\s*[:\-]?\s*([A-Z0-9]{11,16})",norm,re.I)
    if cf:result.tax_code=cf.group(1)
    result.periods=sorted({x[2] for x in _periods(norm)},key=lambda z:(int(z[3:]),int(z[:2])))
    page=1;current_period=result.periods[-1] if result.periods else "";current_cat="non classificata";current_bank="";seen=set()
    labels={'accorded':r"accordato(?! operativo)\s*[:€ ]+([\d., ]+)",'operating_accorded':r"accordato operativo\s*[:€ ]+([\d., ]+)",'used':r"utilizzato\s*[:€ ]+([\d., ]+)",'guaranteed':r"garantito\s*[:€ ]+([\d., ]+)",'overrun':r"(?:sconfinamento|sconfini?)\s*[:€ ]+([\d., ]+)"}
    for idx,line in enumerate(lines):
        pm=re.match(r"\[\[PAGE (\d+)\]\]",line)
        if pm:page=int(pm.group(1));continue
        pl=_periods(line)
        if pl:current_period=pl[-1][2]
        low=line.lower()
        for k,v in CATEGORY_MAP.items():
            if k in low:current_cat=v;break
        if _valid_intermediary(line):current_bank=_clean_bank(line)
        if not current_bank or not current_period:continue
        block=" ".join(lines[max(0,idx-1):min(len(lines),idx+2)]);vals={}
        for fld,pat in labels.items():
            m=re.search(pat,block,re.I)
            if m:vals[fld]=_money(m.group(1))
        if not vals and current_cat!='non classificata' and line==current_bank:
            nums=[_money(x) for x in AMOUNT_RE.findall(" ".join(lines[idx+1:idx+4]))[:5]]
            if len(nums)>=2:
                vals['operating_accorded']=nums[0];vals['used']=nums[1]
                if len(nums)>=3:vals['overrun']=nums[2]
        if vals:
            key=(current_period,current_bank,current_cat,page,tuple(sorted(vals.items())))
            if key not in seen:seen.add(key);result.rows.append(CRRow(period=current_period,intermediary=current_bank,category=current_cat,technical_form=current_cat,source_page=page,raw=block,**vals))
        if 'cointestazione' in low or 'garante' in low or 'fondo di garanzia' in low:
            nums=[_money(x) for x in AMOUNT_RE.findall(line)];result.guarantees.append(Guarantee(current_period,current_bank,line[:150],nums[-2] if len(nums)>1 else (nums[-1] if nums else 0),nums[-1] if nums else 0,'cointestazione' in low,page))
        if 'prima informazione' in low:result.info_requests.append(InfoRequest(current_bank,requested_period=current_period,reason=line[:160],source_page=page))
        if 'rettifica' in low:result.corrections.append(Correction(current_period,current_bank,line[:180],page))
    if not result.rows:result.warnings.append("Nessuna riga quantitativa riclassificata con affidabilita sufficiente.")
    return result
