from __future__ import annotations
from io import BytesIO
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _txt(value) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def build_client_document_pdf(client: dict, documents: Iterable[dict]) -> bytes:
    """Build a professional per-client document index PDF from Airtable records."""
    docs = list(documents)
    out = BytesIO()
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "GoldTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=4 * mm,
    )
    small = ParagraphStyle(
        "Small", parent=styles["BodyText"], fontSize=7.6, leading=9.2,
    )
    header = ParagraphStyle(
        "Header", parent=small, fontName="Helvetica-Bold", textColor=colors.white,
        alignment=TA_CENTER,
    )
    doc = SimpleDocTemplate(
        out,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"FinancePlus - Riepilogo documenti - {_txt(client.get('Cliente'))}",
    )

    story = [
        Paragraph("FINANCE PLUS GOLD", title),
        Paragraph("Riepilogo documentale cliente", styles["Heading2"]),
        Spacer(1, 2 * mm),
    ]

    info = [
        ["Cliente", _txt(client.get("Cliente")), "P.IVA", _txt(client.get("Partita IVA")), "CF", _txt(client.get("Codice Fiscale"))],
        ["PEC", _txt(client.get("PEC")), "REA", _txt(client.get("REA")), "Ultima visura", _txt(client.get("Data estrazione visura"))],
    ]
    info_table = Table(info, colWidths=[20*mm, 70*mm, 18*mm, 42*mm, 15*mm, 70*mm])
    info_table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.3, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), colors.HexColor("#E8EEF7")),
        ("BACKGROUND", (2,0), (2,-1), colors.HexColor("#E8EEF7")),
        ("BACKGROUND", (4,0), (4,-1), colors.HexColor("#E8EEF7")),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
        ("FONTNAME", (2,0), (2,-1), "Helvetica-Bold"),
        ("FONTNAME", (4,0), (4,-1), "Helvetica-Bold"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    story += [info_table, Spacer(1, 5 * mm)]

    story.append(Paragraph(f"Documenti caricati: <b>{len(docs)}</b>", styles["Heading3"]))
    rows = [[
        Paragraph("#", header),
        Paragraph("Documento", header),
        Paragraph("Tipo", header),
        Paragraph("Esercizio", header),
        Paragraph("Data", header),
        Paragraph("Origine", header),
        Paragraph("Stato verifica", header),
        Paragraph("Nome definitivo", header),
        Paragraph("Link Drive", header),
    ]]
    for idx, rec in enumerate(docs, start=1):
        f = rec.get("fields", rec)
        url = _txt(f.get("URL Drive"))
        link = f'<link href="{url}">Apri</link>' if url not in ("-", "") else "-"
        rows.append([
            Paragraph(str(idx), small),
            Paragraph(_txt(f.get("Documento")), small),
            Paragraph(_txt(f.get("Tipo Documento")), small),
            Paragraph(_txt(f.get("Esercizio")), small),
            Paragraph(_txt(f.get("Data Documento")), small),
            Paragraph(_txt(f.get("Origine")), small),
            Paragraph(_txt(f.get("Stato Verifica")), small),
            Paragraph(_txt(f.get("Nome Definitivo")), small),
            Paragraph(link, small),
        ])

    table = Table(
        rows,
        repeatRows=1,
        colWidths=[8*mm, 48*mm, 30*mm, 18*mm, 24*mm, 20*mm, 28*mm, 62*mm, 18*mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#17365D")),
        ("GRID", (0,0), (-1,-1), 0.25, colors.HexColor("#B7C3D0")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,1), (0,-1), "CENTER"),
        ("ALIGN", (3,1), (6,-1), "CENTER"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F7F9FC")]),
    ]))
    story.append(table)
    story += [
        Spacer(1, 4 * mm),
        Paragraph(
            "Nota: il riepilogo riporta esclusivamente i documenti indicizzati in FinancePlus/Airtable al momento della generazione. "
            "I documenti con stato 'Da verificare' richiedono controllo del contenuto prima dell'utilizzo istruttorio.",
            small,
        ),
    ]
    doc.build(story)
    return out.getvalue()
