from __future__ import annotations
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def build_pdf(client: dict, analysis: dict | None = None, cr: dict | None = None, bank: dict | None = None) -> bytes:
    analysis=analysis or {}; cr=cr or {}; bank=bank or {}; out=BytesIO(); styles=getSampleStyleSheet()
    title=ParagraphStyle('GoldTitle',parent=styles['Title'],fontSize=22,leading=26,spaceAfter=12)
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm)
    story=[Paragraph('FINANCE PLUS GOLD',title),Paragraph('Dossier bancario professionale',styles['Heading2']),Spacer(1,8*mm)]
    name=client.get('Cliente') or client.get('Ragione sociale') or 'Cliente da verificare'
    rows=[['Cliente',name],['P.IVA',client.get('Partita IVA','N/D')],['PEC',client.get('PEC','N/D')],['ATECO',client.get('ATECO','N/D')],['Sede',client.get('Sede legale','N/D')]]
    t=Table(rows,colWidths=[45*mm,115*mm]); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.25,colors.grey),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),6)])); story += [t,Spacer(1,8*mm)]
    for heading,data in [('Analisi economico-finanziaria',analysis),('Centrale Rischi',cr),('Conti correnti',bank)]:
        story += [Paragraph(heading,styles['Heading2']),Paragraph(str(data) if data else 'Non disponibile / non analizzato.',styles['BodyText']),Spacer(1,5*mm)]
    story += [Paragraph('Nota metodologica',styles['Heading2']),Paragraph('I valori mancanti restano N/D. Rating, DSCR, PFN e capacità finanziabile non vengono ricostruiti quando i dati sorgente non sono sufficienti.',styles['BodyText'])]
    doc.build(story); return out.getvalue()
