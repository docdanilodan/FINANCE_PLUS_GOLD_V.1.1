from __future__ import annotations

from datetime import datetime
from html import escape
from io import BytesIO
import re
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


BRAND_BLUE = colors.HexColor("#123B5D")
BRAND_BRONZE = colors.HexColor("#B7791F")
LIGHT_BLUE = colors.HexColor("#EAF1F6")
LIGHT_GREY = colors.HexColor("#F4F6F8")
MID_GREY = colors.HexColor("#667085")


def _first(fields: dict, *names: str, default: str = "") -> str:
    for name in names:
        value = fields.get(name)
        if value not in (None, "", []):
            if isinstance(value, list):
                return ", ".join(str(v) for v in value)
            return str(value)
    return default


def document_summary_rows(records: Iterable[dict]) -> list[dict]:
    rows: list[dict] = []
    for record in records:
        fields = record.get("fields", {}) if isinstance(record, dict) else {}
        rows.append(
            {
                "Documento": _first(fields, "Documento", "Nome file", "File", "Nome Definitivo", default="—"),
                "Tipo Documento": _first(fields, "Tipo Documento", "Tipo", "Categoria", default="—"),
                "Esercizio": _first(fields, "Esercizio", "Anno", default="—"),
                "Data Documento": _first(fields, "Data Documento", "Data", default="—"),
                "Origine": _first(fields, "Origine", "Fonte", "Provenienza", default="—"),
                "Nome Definitivo": _first(fields, "Nome Definitivo", "Nome definitivo", default="—"),
                "Stato Verifica": _first(fields, "Stato Verifica", "Stato verifica", default="—"),
                "URL Drive": _first(fields, "URL Drive", "Drive URL", "Link Drive", default=""),
            }
        )
    rows.sort(
        key=lambda row: (
            str(row.get("Esercizio", "")),
            str(row.get("Data Documento", "")),
            str(row.get("Tipo Documento", "")),
            str(row.get("Documento", "")),
        ),
        reverse=True,
    )
    return rows


def safe_client_filename(client_name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(client_name or "Cliente").strip())
    cleaned = cleaned.strip("._-") or "Cliente"
    return f"{cleaned}_Riepilogo_Documenti.pdf"


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(str(text or "—")), style)


def build_client_document_pdf(client_fields: dict, document_records: Iterable[dict]) -> bytes:
    rows = document_summary_rows(document_records)
    client_name = _first(client_fields, "Cliente", "Ragione sociale", default="Cliente")
    vat = _first(client_fields, "Partita IVA", default="—")
    tax_code = _first(client_fields, "Codice Fiscale", default="—")
    rea = _first(client_fields, "REA", default="—")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
        title=f"FinancePlus - Riepilogo documenti - {client_name}",
        author="FinancePlus GOLD",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FPTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=BRAND_BLUE,
        alignment=TA_LEFT,
        spaceAfter=4 * mm,
    )
    meta_style = ParagraphStyle(
        "FPMeta",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.7,
        leading=11,
        textColor=colors.HexColor("#344054"),
    )
    small_style = ParagraphStyle(
        "FPSmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=9,
        textColor=colors.HexColor("#1D2939"),
        alignment=TA_LEFT,
    )
    small_center = ParagraphStyle(
        "FPSmallCenter",
        parent=small_style,
        alignment=TA_CENTER,
    )
    header_style = ParagraphStyle(
        "FPHeader",
        parent=small_center,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        fontSize=7.0,
        leading=8,
    )

    story = [Paragraph("FINANCEPLUS GOLD - RIEPILOGO DOCUMENTALE CLIENTE", title_style)]

    meta = Table(
        [
            [_p("Cliente", meta_style), _p(client_name, meta_style), _p("Partita IVA", meta_style), _p(vat, meta_style)],
            [_p("Codice Fiscale", meta_style), _p(tax_code, meta_style), _p("REA", meta_style), _p(rea, meta_style)],
            [_p("Documenti caricati", meta_style), _p(str(len(rows)), meta_style), _p("Generato il", meta_style), _p(datetime.now().strftime("%d/%m/%Y %H:%M"), meta_style)],
        ],
        colWidths=[32 * mm, 90 * mm, 32 * mm, 100 * mm],
    )
    meta.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
                ("BACKGROUND", (2, 0), (2, -1), LIGHT_BLUE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D0D5DD")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E4E7EC")),
            ]
        )
    )
    story.extend([meta, Spacer(1, 5 * mm)])

    if not rows:
        story.append(Paragraph("Nessun documento collegato al cliente.", meta_style))
    else:
        headers = ["N.", "Documento", "Tipo", "Esercizio", "Data", "Origine", "Nome definitivo", "Stato", "File"]
        data = [[Paragraph(h, header_style) for h in headers]]
        for idx, row in enumerate(rows, start=1):
            url = str(row.get("URL Drive", "") or "").strip()
            link = (
                Paragraph(f'<link href="{escape(url, quote=True)}" color="#123B5D"><u>Apri</u></link>', small_center)
                if url.startswith(("http://", "https://"))
                else _p("—", small_center)
            )
            data.append(
                [
                    _p(str(idx), small_center),
                    _p(row["Documento"], small_style),
                    _p(row["Tipo Documento"], small_style),
                    _p(row["Esercizio"], small_center),
                    _p(row["Data Documento"], small_center),
                    _p(row["Origine"], small_style),
                    _p(row["Nome Definitivo"], small_style),
                    _p(row["Stato Verifica"], small_center),
                    link,
                ]
            )

        table = Table(
            data,
            repeatRows=1,
            colWidths=[8 * mm, 44 * mm, 28 * mm, 17 * mm, 23 * mm, 26 * mm, 52 * mm, 27 * mm, 15 * mm],
            hAlign="LEFT",
        )
        table_style = [
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_BLUE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                table_style.append(("BACKGROUND", (0, i), (-1, i), LIGHT_GREY))
        table.setStyle(TableStyle(table_style))
        story.append(table)

    def footer(canvas, document):
        canvas.saveState()
        width, _ = landscape(A4)
        canvas.setStrokeColor(BRAND_BRONZE)
        canvas.setLineWidth(1.2)
        canvas.line(10 * mm, 9 * mm, width - 10 * mm, 9 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MID_GREY)
        canvas.drawString(10 * mm, 5.5 * mm, "FinancePlus GOLD - Riepilogo documentale")
        canvas.drawRightString(width - 10 * mm, 5.5 * mm, f"Pagina {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
