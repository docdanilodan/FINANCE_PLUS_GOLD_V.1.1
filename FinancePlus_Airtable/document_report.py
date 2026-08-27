from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any, Dict, Iterable, List

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#17324D")
COPPER = colors.HexColor("#B87333")
LIGHT = colors.HexColor("#F3F5F7")
MID = colors.HexColor("#D8DEE6")
TEXT = colors.HexColor("#222222")
MUTED = colors.HexColor("#5E6872")


def _text(value: Any, fallback: str = "-") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return fallback
    text = (
        text.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
        .replace("\u2026", "...")
    )
    return text.encode("cp1252", "replace").decode("cp1252")


def _para(value: Any, style: ParagraphStyle, fallback: str = "-") -> Paragraph:
    return Paragraph(escape(_text(value, fallback)).replace("\n", "<br/>"), style)


def _document_name(row: Dict[str, Any]) -> str:
    for key in ("Nome Definitivo", "Documento", "Nome Originale", "Nome IA Suggerito"):
        value = row.get(key)
        if value is not None and str(value).strip() and str(value).lower() != "nan":
            return str(value).strip()
    return "Documento senza nome"


def _page_footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = landscape(A4)
    canvas.setStrokeColor(MID)
    canvas.setLineWidth(0.4)
    canvas.line(14 * mm, 10 * mm, width - 14 * mm, 10 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(14 * mm, 6.5 * mm, "FinancePlus Airtable - Riepilogo documentale")
    canvas.drawRightString(width - 14 * mm, 6.5 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


def build_client_documents_pdf(
    client: Dict[str, Any],
    documents: Iterable[Dict[str, Any]],
) -> bytes:
    """Return a professional landscape-A4 PDF with every document linked to a client."""
    docs: List[Dict[str, Any]] = [dict(item) for item in documents]

    def sort_key(row: Dict[str, Any]):
        return (
            _text(row.get("Data Documento"), "9999-12-31"),
            _text(row.get("Tipo Documento"), ""),
            _document_name(row),
        )

    docs.sort(key=sort_key)

    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=13 * mm,
        bottomMargin=15 * mm,
        title=f"Riepilogo documenti - {_text(client.get('Cliente'), 'Cliente')}",
        author="FinancePlus Airtable",
        subject="Elenco documenti collegati al cliente",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FinancePlusTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=21,
        textColor=NAVY,
        alignment=TA_LEFT,
        spaceAfter=4 * mm,
    )
    sub_style = ParagraphStyle(
        "FinancePlusSub",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=MUTED,
        spaceAfter=2 * mm,
    )
    meta_label = ParagraphStyle(
        "MetaLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=NAVY,
    )
    meta_value = ParagraphStyle(
        "MetaValue",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=TEXT,
    )
    header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=7.1,
        leading=8.5,
        textColor=colors.white,
        alignment=TA_LEFT,
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=6.7,
        leading=8.2,
        textColor=TEXT,
        alignment=TA_LEFT,
    )
    link_style = ParagraphStyle(
        "TableLink",
        parent=cell_style,
        textColor=NAVY,
    )

    story = []
    client_name = _text(client.get("Cliente"), "Cliente")
    story.append(Paragraph("Riepilogo documentale cliente", title_style))
    story.append(
        Paragraph(
            f"Elenco completo dei documenti indicizzati in FinancePlus Airtable per <b>{escape(client_name)}</b>.",
            sub_style,
        )
    )

    meta_data = [
        [
            _para("Cliente", meta_label),
            _para(client_name, meta_value),
            _para("Partita IVA", meta_label),
            _para(client.get("Partita IVA"), meta_value),
            _para("Codice fiscale", meta_label),
            _para(client.get("Codice Fiscale"), meta_value),
        ],
        [
            _para("REA", meta_label),
            _para(client.get("REA"), meta_value),
            _para("PEC", meta_label),
            _para(client.get("PEC"), meta_value),
            _para("Documenti", meta_label),
            _para(len(docs), meta_value),
        ],
        [
            _para("Ultimo bilancio", meta_label),
            _para(client.get("Ultimo bilancio disponibile"), meta_value),
            _para("CR aggiornata al", meta_label),
            _para(client.get("CR aggiornata al"), meta_value),
            _para("Generato il", meta_label),
            _para(datetime.now().strftime("%d/%m/%Y %H:%M"), meta_value),
        ],
    ]
    meta_table = Table(
        meta_data,
        colWidths=[24 * mm, 48 * mm, 25 * mm, 42 * mm, 27 * mm, 47 * mm],
        hAlign="LEFT",
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.45, MID),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, MID),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(KeepTogether([meta_table, Spacer(1, 5 * mm)]))

    if not docs:
        story.append(Paragraph("Nessun documento collegato al cliente.", styles["BodyText"]))
    else:
        headers = [
            "N.",
            "Documento",
            "Tipo",
            "Esercizio",
            "Data",
            "Pratica",
            "Origine",
            "Stato",
            "Drive",
        ]
        table_data = [[_para(h, header_style) for h in headers]]

        for index, row in enumerate(docs, start=1):
            url = _text(row.get("URL Drive"), "")
            drive_cell = _para("-", cell_style)
            if url.startswith("http://") or url.startswith("https://"):
                safe_url = escape(url, quote=True)
                drive_cell = Paragraph(f'<link href="{safe_url}">Apri</link>', link_style)

            table_data.append(
                [
                    _para(index, cell_style),
                    _para(_document_name(row), cell_style),
                    _para(row.get("Tipo Documento"), cell_style),
                    _para(row.get("Esercizio"), cell_style),
                    _para(row.get("Data Documento"), cell_style),
                    _para(row.get("Pratica ID"), cell_style),
                    _para(row.get("Origine"), cell_style),
                    _para(row.get("Stato Verifica"), cell_style),
                    drive_cell,
                ]
            )

        doc_table = Table(
            table_data,
            repeatRows=1,
            colWidths=[8 * mm, 62 * mm, 31 * mm, 17 * mm, 23 * mm, 31 * mm, 25 * mm, 26 * mm, 18 * mm],
            hAlign="LEFT",
        )
        doc_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("LINEBELOW", (0, 0), (-1, 0), 1.2, COPPER),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                    ("GRID", (0, 0), (-1, -1), 0.3, MID),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (0, 1), (0, -1), "CENTER"),
                    ("ALIGN", (3, 1), (4, -1), "CENTER"),
                    ("ALIGN", (8, 1), (8, -1), "CENTER"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(doc_table)
        story.append(Spacer(1, 4 * mm))
        story.append(
            Paragraph(
                "Nota: il report elenca i record documentali presenti in Airtable al momento della generazione. "
                "Il link Drive e riportato solo quando disponibile nel relativo record.",
                sub_style,
            )
        )

    pdf.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
