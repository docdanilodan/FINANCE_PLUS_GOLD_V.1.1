from __future__ import annotations
from collections import Counter
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def _txt(value) -> str:
    if value in (None, "", []):
        return "—"
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or "—"
    return str(value)


def _pct(value) -> str:
    if value in (None, ""):
        return "N/D"
    try:
        v = float(value)
        if 0 <= v <= 1:
            v *= 100
        return f"{v:.0f}%"
    except Exception:
        return _txt(value)


def _money(value) -> str:
    if isinstance(value, (int, float)):
        return (f"€ {value:,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")
    return _txt(value)


def build_client_documents_pdf(client_name: str, documents: list[dict], practices: list[dict] | None = None, client_fields: dict | None = None) -> bytes:
    practices = practices or []
    client_fields = client_fields or {}
    out = BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(out, pagesize=page, leftMargin=10*mm, rightMargin=10*mm, topMargin=10*mm, bottomMargin=10*mm, title=f"F_P_NEUTRO - Report Cliente - {client_name}")
    styles = getSampleStyleSheet()
    title = ParagraphStyle("NeutralTitle", parent=styles["Title"], fontSize=18, leading=22, textColor=colors.HexColor("#17365D"), spaceAfter=6)
    section = ParagraphStyle("Section", parent=styles["Heading2"], fontSize=12, leading=15, textColor=colors.HexColor("#17365D"), spaceBefore=4, spaceAfter=5)
    small = ParagraphStyle("Small", parent=styles["BodyText"], fontSize=7.5, leading=9)
    body = ParagraphStyle("BodyNeutral", parent=styles["BodyText"], fontSize=8.5, leading=11)

    story = [Paragraph("F_P_NEUTRO V_1.1 - REPORT CLIENTE", title), Paragraph(f"<b>{_txt(client_name)}</b>", styles["Heading2"]), Paragraph("Anagrafica, controllo dossier e archivio documentale", body), Spacer(1, 5*mm)]

    identity = [
        ["Partita IVA", _txt(client_fields.get("Partita IVA")), "Codice Fiscale", _txt(client_fields.get("Codice Fiscale"))],
        ["PEC", _txt(client_fields.get("PEC")), "REA", _txt(client_fields.get("REA"))],
        ["Sede legale", _txt(client_fields.get("Sede legale")), "ATECO", _txt(client_fields.get("ATECO"))],
        ["Amministratore", _txt(client_fields.get("Rappresentante/Amministratore")), "Capitale sociale", _money(client_fields.get("Capitale sociale EUR"))],
    ]
    itable = Table(identity, colWidths=[31*mm, 88*mm, 31*mm, 112*mm])
    itable.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#E9EEF5")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#E9EEF5")),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#B7C5D5")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [Paragraph("Anagrafica cliente", section), itable, Spacer(1, 5*mm)]

    completeness = [_pct(r.get("fields", r).get("Completezza dossier")) for r in practices if r.get("fields", r).get("Completezza dossier") not in (None, "")]
    states = list(dict.fromkeys(str(r.get("fields", r).get("Stato")) for r in practices if r.get("fields", r).get("Stato")))
    docs_state = list(dict.fromkeys(str(r.get("fields", r).get("Stato documentazione")) for r in practices if r.get("fields", r).get("Stato documentazione")))
    control = [
        ["Documenti", str(len(documents)), "Pratiche", str(len(practices)), "Rating", _txt(client_fields.get("Rating FinancePlus"))],
        ["Ultimo bilancio", _txt(client_fields.get("Ultimo bilancio disponibile")), "CR aggiornata al", _txt(client_fields.get("CR aggiornata al")), "Completezza", ", ".join(completeness) or "N/D"],
        ["Stato pratica", ", ".join(states) or "—", "Stato documentazione", ", ".join(docs_state) or "—", "Ultima visura", _txt(client_fields.get("Data estrazione visura"))],
    ]
    ctable = Table(control, colWidths=[31*mm,58*mm,34*mm,58*mm,36*mm,45*mm])
    ctable.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#E9EEF5")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#E9EEF5")),("BACKGROUND",(4,0),(4,-1),colors.HexColor("#E9EEF5")),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"),("FONTNAME",(4,0),(4,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#B7C5D5")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [Paragraph("Controllo dossier", section), ctable, Spacer(1, 5*mm)]

    missing = " | ".join(dict.fromkeys(str(r.get("fields",r).get("Documenti mancanti")) for r in practices if r.get("fields",r).get("Documenti mancanti"))) or "—"
    actions = " | ".join(dict.fromkeys(str(r.get("fields",r).get("Prossima azione")) for r in practices if r.get("fields",r).get("Prossima azione"))) or "—"
    deadlines = ", ".join(dict.fromkeys(str(r.get("fields",r).get("Scadenza prossima azione")) for r in practices if r.get("fields",r).get("Scadenza prossima azione"))) or "—"
    alerts = " | ".join(dict.fromkeys(str(r.get("fields",r).get("Alert e criticità")) for r in practices if r.get("fields",r).get("Alert e criticità"))) or "—"
    action_rows = [["Documenti mancanti",Paragraph(missing,body)],["Prossima azione",Paragraph(actions,body)],["Scadenza",deadlines],["Alert / criticità",Paragraph(alerts,body)]]
    atable = Table(action_rows, colWidths=[40*mm,222*mm])
    atable.setStyle(TableStyle([("BACKGROUND",(0,0),(0,-1),colors.HexColor("#FFF2CC")),("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#C9B458")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [Paragraph("Azioni e criticità", section), atable, Spacer(1, 5*mm)]

    counts = Counter(str(r.get("fields",r).get("Tipo Documento") or r.get("fields",r).get("Categoria") or "Altro") for r in documents)
    if counts:
        catrows = [["Categoria", "N. documenti"]] + [[k, str(v)] for k,v in sorted(counts.items(), key=lambda x:(-x[1],x[0].casefold()))]
        cattable = Table(catrows, colWidths=[110*mm,35*mm])
        cattable.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#E9EEF5")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),8),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#B7C5D5")),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
        story += [Paragraph("Documenti per categoria", section), cattable]

    story += [PageBreak(), Paragraph("ARCHIVIO DOCUMENTALE COMPLETO", title), Paragraph(f"Cliente: <b>{_txt(client_name)}</b> - Documenti indicizzati: <b>{len(documents)}</b>", body), Spacer(1,5*mm)]
    headers=["N.","Documento","Tipo","Esercizio","Data","Nome originale","Origine","Stato","File / ZIP"]
    rows=[headers]
    for idx,record in enumerate(documents,start=1):
        f=record.get("fields",record)
        link=f.get("URL Drive") or f.get("Archivio ZIP sorgente") or ""
        label="File" if f.get("URL Drive") else ("ZIP" if f.get("Archivio ZIP sorgente") else "—")
        rows.append([str(idx),Paragraph(_txt(f.get("Documento")),small),Paragraph(_txt(f.get("Tipo Documento")),small),_txt(f.get("Esercizio")),_txt(f.get("Data Documento")),Paragraph(_txt(f.get("Nome Originale") or f.get("Percorso nel pacchetto")),small),_txt(f.get("Origine")),_txt(f.get("Stato Verifica")),Paragraph(f'<link href="{link}">{label}</link>' if link else "—",small)])
    widths=[8,48,27,16,20,56,18,24,18]
    table=Table(rows,colWidths=[w*mm for w in widths],repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17365D")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),7.5),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.25,colors.grey),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F7F9FB")]),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(table)

    story += [PageBreak(), Paragraph("DETTAGLIO PRATICHE", title)]
    if not practices:
        story.append(Paragraph("Nessuna pratica collegata al cliente oppure dati pratica non disponibili.", body))
    else:
        pheaders=["Pratica","Tipo","Istituto","Stato","Completezza","Documenti mancanti","Alert / criticità","Prossima azione","Scadenza","Responsabile"]
        prows=[pheaders]
        for record in practices:
            f=record.get("fields",record)
            prows.append([Paragraph(_txt(f.get("Pratica ID")),small),Paragraph(_txt(f.get("Tipo Pratica")),small),Paragraph(_txt(f.get("Istituto")),small),Paragraph(_txt(f.get("Stato")),small),_pct(f.get("Completezza dossier")),Paragraph(_txt(f.get("Documenti mancanti")),small),Paragraph(_txt(f.get("Alert e criticità")),small),Paragraph(_txt(f.get("Prossima azione")),small),_txt(f.get("Scadenza prossima azione")),Paragraph(_txt(f.get("Responsabile pratica")),small)])
        pwidths=[24,24,24,20,18,43,43,43,24,30]
        ptable=Table(prows,colWidths=[w*mm for w in pwidths],repeatRows=1)
        ptable.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17365D")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,0),7.2),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),0.25,colors.grey),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
        story.append(ptable)
    story += [Spacer(1,5*mm),Paragraph("Nota: il report riporta esclusivamente i dati presenti in Airtable. I valori mancanti non vengono ricostruiti o inventati.",body)]
    doc.build(story)
    return out.getvalue()
