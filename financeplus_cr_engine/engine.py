from __future__ import annotations
from collections import defaultdict
from dataclasses import asdict
from .models import ParsedCR, Analysis, AuditResult

def _rating(score:int):
    if score>=90:return "AAA",0.25
    if score>=80:return "AA",0.50
    if score>=70:return "A",1.00
    if score>=60:return "BBB",2.00
    if score>=45:return "BB",5.00
    return "B/D",10.00

def analyze(parsed:ParsedCR)->Analysis:
    errors=[]; warnings=list(parsed.warnings); valid_rows=[]
    for r in parsed.rows:
        vals=[r.accorded,r.operating_accorded,r.used,r.guaranteed,r.overrun]
        if any(v<0 for v in vals): errors.append(f"Importo negativo: {r.intermediary} {r.period}"); continue
        if r.accorded and r.operating_accorded and r.operating_accorded>r.accorded*1.05:
            errors.append(f"Accordato operativo superiore all'accordato: {r.intermediary} {r.period}"); continue
        if r.used>0 and not (r.operating_accorded or r.accorded): warnings.append(f"Utilizzato senza accordato omogeneo: {r.intermediary} {r.period}")
        valid_rows.append(r)
    periods=sorted({r.period for r in valid_rows}, key=lambda z:(int(z[3:]),int(z[:2])))[-36:]
    monthly=[]
    for p in periods:
        rows=[r for r in valid_rows if r.period==p]; ao=sum(r.operating_accorded for r in rows); acc=sum(r.accorded for r in rows); used=sum(r.used for r in rows); over=sum(r.overrun for r in rows); guar=sum(r.guaranteed for r in rows); sat=(used/ao*100) if ao>0 else None
        if sat is not None and sat>500: errors.append(f"Saturazione incompatibile {sat:.1f}% nel periodo {p}")
        monthly.append({'period':p,'accorded':acc,'operating_accorded':ao,'used':used,'overrun':over,'guaranteed':guar,'saturation':sat,'banks':len({r.intermediary for r in rows})})
    latest=periods[-1] if periods else ''; lr=[r for r in valid_rows if r.period==latest]
    def rank(field):
        d=defaultdict(float)
        for r in lr:d[r.intermediary]+=getattr(r,field)
        total=sum(d.values()); return [{'intermediary':k,'value':v,'weight':(v/total*100 if total else 0)} for k,v in sorted(d.items(),key=lambda x:x[1],reverse=True)]
    ranks={x:rank(x) for x in ('operating_accorded','used','overrun','guaranteed')}; anomalies=[]; score=100
    if any(m['overrun']>0 for m in monthly): anomalies.append('Sconfini rilevati'); score-=12
    if any(m['saturation'] is not None and m['saturation']>95 for m in monthly): anomalies.append('Saturazione superiore al 95%'); score-=10
    if any(r.category=='sofferenze' and r.used>0 for r in valid_rows): anomalies.append('Sofferenze'); score-=45
    if parsed.corrections: anomalies.append('Rettifiche da verificare'); score-=4
    if len(parsed.info_requests)>=4: anomalies.append('Numerose richieste di prima informazione'); score-=5
    if not valid_rows: score=0; errors.append('Nessun dato quantitativo affidabile: generazione professionale bloccata.')
    score=max(0,min(100,score)); rating,pd=_rating(score); audit=AuditResult(valid=(not errors),errors=errors,warnings=warnings)
    return Analysis(parsed.subject,parsed.tax_code,periods,monthly,ranks,score,rating,pd,anomalies,audit,[asdict(x) for x in parsed.guarantees],[asdict(x) for x in parsed.info_requests],[asdict(x) for x in parsed.corrections])
