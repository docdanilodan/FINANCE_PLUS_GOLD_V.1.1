from __future__ import annotations
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from .models import Analysis

NAVY=HexColor('#102A43'); COPPER=HexColor('#C46B32'); GREY=HexColor('#6B7280')

def _eur(v): return f"EUR {v:,.0f}".replace(',', '.')

def generate_pdf(a: Analysis, output: str|Path, allow_invalid: bool=False):
    if not a.audit.valid and not allow_invalid:raise ValueError('Controllo di congruita non superato: '+'; '.join(a.audit.errors))
    out=Path(output); c=canvas.Canvas(str(out),pagesize=A4); w,h=A4
    c.setFillColor(NAVY); c.rect(0,0,w,h,fill=1,stroke=0); c.setFillColorRGB(1,1,1)
    c.setFont('Helvetica-Bold',26); c.drawString(20*mm,250*mm,'FINANCEPLUS - ANALISI CR 36 MESI')
    c.setFont('Helvetica-Bold',16); c.drawString(20*mm,225*mm,a.subject[:55])
    c.setFont('Helvetica',10); c.drawString(20*mm,210*mm,('Periodo: '+a.periods[0]+' - '+a.periods[-1]) if a.periods else 'Periodo non disponibile'); c.showPage()
    c.setFillColor(NAVY); c.setFont('Helvetica-Bold',20); c.drawString(18*mm,275*mm,'Sintesi e controlli'); c.setStrokeColor(COPPER); c.line(18*mm,270*mm,195*mm,270*mm)
    c.setFont('Helvetica-Bold',12); c.drawString(18*mm,252*mm,f'Score: {a.score}/100   Rating: {a.rating}   PD indicativa: {a.pd:.2f}%')
    c.setFont('Helvetica',9); y=235*mm
    for text in ([f'Audit: {"OK" if a.audit.valid else "BLOCCATO"}']+['Anomalia: '+x for x in a.anomalies]+['Avviso: '+x for x in a.audit.warnings]+['Errore: '+x for x in a.audit.errors]):
        c.drawString(18*mm,y,text[:115]); y-=6*mm
        if y<25*mm: break
    c.showPage(); rows=a.monthly or []; chunks=[rows[i:i+24] for i in range(0,len(rows),24)] or [[]]
    for chunk_no,chunk in enumerate(chunks,1):
        c.setFillColor(NAVY); c.setFont('Helvetica-Bold',18); c.drawString(18*mm,275*mm,f'Andamento mensile CR - {chunk_no}/{len(chunks)}')
        y=258*mm; c.setFont('Helvetica-Bold',7); c.drawString(18*mm,y,'Periodo'); c.drawString(45*mm,y,'Accordato op.'); c.drawString(85*mm,y,'Utilizzato'); c.drawString(120*mm,y,'Sconfino'); c.drawString(150*mm,y,'Saturazione')
        y-=6*mm; c.setFont('Helvetica',7)
        for m in chunk:
            c.drawString(18*mm,y,m['period']); c.drawString(45*mm,y,_eur(m['operating_accorded'])); c.drawString(85*mm,y,_eur(m['used'])); c.drawString(120*mm,y,_eur(m['overrun'])); c.drawString(150*mm,y,'n.d.' if m['saturation'] is None else f"{m['saturation']:.1f}%"); y-=8*mm
        c.showPage()
    c.setFillColor(NAVY); c.setFont('Helvetica-Bold',18); c.drawString(18*mm,275*mm,'Ranking banche - ultimo periodo'); y=255*mm; c.setFont('Helvetica',8)
    for key,label in [('operating_accorded','Accordato operativo'),('used','Utilizzato'),('overrun','Sconfini')]:
        c.setFont('Helvetica-Bold',10); c.drawString(18*mm,y,label); y-=6*mm; c.setFont('Helvetica',8)
        for row in a.bank_ranking.get(key,[])[:10]:
            c.drawString(22*mm,y,f"{row['intermediary'][:55]} - {_eur(row['value'])} - {row['weight']:.1f}%"); y-=5*mm
            if y<25*mm: break
        y-=5*mm
        if y<25*mm: break
    c.save(); return out
