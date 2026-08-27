from __future__ import annotations
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def _txt(value) -> str:
    if value in (None, ""):
        return "—"
    return str(value)


def _pct(value) -> str:
    if value in (None, ""):
        return "N/D"
    try:
        v=float(value)
        if 0 <= v <= 1:
            v *= 100
        return f"{v:.0f}%"
    except Exception:
        return _txt(value)


def build_client_documents_pdf(client_name: str, documents: list[dict], practices: list[dict] | None = None) -> bytes:
    practices = practices or []
    out = BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(out,pagesize=page,leftMargin=10*mm,rightMargin=10*mm,topMargin=10*mm,bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("GoldTitle", parent=styles["Title"], fontSize=18, leading=22, spaceAfter=6)
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=7.5, leading=9)
    body = ParagraphStyle("BodyGold", parent=styles["BodyText"], fontSize=9, leading=12)

    story=[Paragraph("FINANCE PLUS GOLD — RIEPILOGO DOCUMENTI CLIENTE",title),Paragraph(f"Cliente: <b>{_txt(client_name)}</b>",styles["Heading2"]),Paragraph(f"Documenti indicizzati: <b>{len(documents)}</b>",styles["BodyText"]),Spacer(1,5*mm)]
    headers=["N.","Documento","Tipo","Esercizio","Data","Nome originale","Nome definitivo","Origine","Stato","Drive"]
    rows=[headers]
    for idx,record in enumerate(documents,start=1):
        f=record.get("fields",record); link=f.get("URL Drive") or ""
        rows.append([str(idx),Paragraph(_txt(f.get("Documento")),small),Paragraph(_txt(f.get("Tipo Documento")),small),_txt(f.get("Esercizio")),_txt(f.get("Data Documento")),Paragraph(_txt(f.get("Nome Originale")),small),Paragraph(_txt(f.get("Nome Definitivo")),small),_txt(f.get("Origine")),_txt(f.get("Stato Verifica")),Paragraph(f'<link href="{link}">Apri</link>' if link else "—",small)])
    widths=[8,38,25,15,20,42,42,18,22,14]
    table=Table(rows,colWidths=[w*mm for w in widths],repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E9EEF5")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),7.5),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.25,colors.grey),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(table)

    story += [PageBreak(), Paragraph("CONTROLLO PRATICHE E COMPLETEZZA DOSSIER", title), Paragraph(f"Cliente: <b>{_txt(client_name)}</b>", styles["Heading2"]), Spacer(1,4*mm)]
    if not practices:
        story.append(Paragraph("Nessuna pratica collegata al cliente oppure dati pratica non disponibili.", body))
    else:
        pheaders=["Pratica","Tipo","Istituto","Stato","Completezza","Documenti mancanti","Alert / criticità","Prossima azione","Scadenza","Responsabile"]
        prows=[pheaders]
        for record in practices:
            f=record.get("fields",record)
            prows.append([
                Paragraph(_txt(f.get("Pratica ID")),small),
                Paragraph(_txt(f.get("Tipo Pratica")),small),
                Paragraph(_txt(f.get("Istituto")),small),
                Paragraph(_txt(f.get("Stato")),small),
                _pct(f.get("Completezza dossier")),
                Paragraph(_txt(f.get("Documenti mancanti")),small),
                Paragraph(_txt(f.get("Alert e criticità")),small),
                Paragraph(_txt(f.get("Prossima azione")),small),
                _txt(f.get("Scadenza prossima azione")),
                Paragraph(_txt(f.get("Responsabile pratica")),small),
            ])
        pwidths=[24,24,24,20,18,43,43,43,24,30]
        ptable=Table(prows,colWidths=[w*mm for w in pwidths],repeatRows=1)
        ptable.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E9EEF5")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),7.2),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.25,colors.grey),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
        story.append(ptable)
        story += [Spacer(1,5*mm),Paragraph("Nota: completezza, documenti mancanti e alert sono riportati dai campi della pratica FinancePlus. Se un dato non è disponibile viene indicato N/D o —; il PDF non ricostruisce valori mancanti.",body)]

    doc.build(story)
    return out.getvalue()
