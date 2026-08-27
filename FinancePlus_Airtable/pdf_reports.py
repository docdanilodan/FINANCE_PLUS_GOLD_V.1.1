from __future__ import annotations

from datetime import date
from io import BytesIO
import re
from typing import Any, Dict
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NAVY = colors.HexColor("#0B1F33")
COPPER = colors.HexColor("#B87333")
LIGHT_BLUE = colors.HexColor("#EEF3F7")
LIGHT_COPPER = colors.HexColor("#F5EEE8")
MID_GRAY = colors.HexColor("#6B7280")
LIGHT_GRAY = colors.HexColor("#F7F8FA")
BORDER = colors.HexColor("#D6DCE2")


def _missing(value: Any) -> bool:
    if value is None or value == "":
        return True
    try:
        result = pd.isna(value)
        return bool(result) if isinstance(result, (bool, type(pd.NA))) else False
    except Exception:
        return False


def _text(value: Any, default: str = "—") -> str:
    if _missing(value):
        return default
    return str(value).strip() or default


def _format_year(value: Any) -> str:
    if _missing(value):
        return "—"
    try:
        return str(int(float(value)))
    except Exception:
        return _text(value)


def _format_date(value: Any) -> str:
    if _missing(value):
        return "—"
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return _text(value)
        return parsed.strftime("%d/%m/%Y")
    except Exception:
        return _text(value)


def _document_name(row: pd.Series) -> str:
    for field in ("Nome Definitivo", "Documento", "Nome IA Suggerito", "Nome Originale"):
        value = row.get(field)
        if not _missing(value):
            text = str(value).strip()
            if text:
                return text
    return "Documento senza nome"


def build_documents_summary_df(documents: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "N.", "Tipo", "Esercizio", "Data", "Documento", "Pratica",
        "Origine", "Stato", "Drive",
    ]
    if documents is None or documents.empty:
        return pd.DataFrame(columns=columns)

    work = documents.copy()
    work["_sort_year"] = pd.to_numeric(work.get("Esercizio"), errors="coerce")
    work["_sort_date"] = pd.to_datetime(work.get("Data Documento"), errors="coerce")
    work["_sort_name"] = work.apply(_document_name, axis=1)
    work = work.sort_values(
        ["_sort_year", "_sort_date", "_sort_name"],
        ascending=[False, False, True],
        na_position="last",
    )

    rows = []
    for number, (_, row) in enumerate(work.iterrows(), start=1):
        drive = "" if _missing(row.get("URL Drive")) else str(row.get("URL Drive")).strip()
        rows.append(
            {
                "N.": number,
                "Tipo": _text(row.get("Tipo Documento")),
                "Esercizio": _format_year(row.get("Esercizio")),
                "Data": _format_date(row.get("Data Documento")),
                "Documento": _document_name(row),
                "Pratica": _text(row.get("Pratica ID")),
                "Origine": _text(row.get("Origine")),
                "Stato": _text(row.get("Stato Verifica")),
                "Drive": drive or None,
            }
        )
    return pd.DataFrame(rows, columns=columns)


def safe_pdf_filename(client_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(client_name or "Cliente")).strip("_")
    slug = slug[:90] or "Cliente"
    return f"FinancePlus_Riepilogo_Documenti_{slug}.pdf"


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(_text(value)), style)


def _page_footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = landscape(A4)
    canvas.setStrokeColor(COPPER)
    canvas.setLineWidth(0.7)
    canvas.line(14 * mm, 11 * mm, width - 14 * mm, 11 * mm)
    canvas.setFillColor(MID_GRAY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(14 * mm, 6.8 * mm, "FinancePlus AI — Riepilogo documentale cliente")
    canvas.drawRightString(width - 14 * mm, 6.8 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


def build_client_documents_pdf(client: Dict[str, Any], documents: pd.DataFrame) -> bytes:
    summary = build_documents_summary_df(documents)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"FinancePlus - Riepilogo documenti - {_text(client.get('Cliente'), 'Cliente')}",
        author="FinancePlus AI",
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
    subtitle_style = ParagraphStyle(
        "FinancePlusSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=MID_GRAY,
        spaceAfter=3 * mm,
    )
    label_style = ParagraphStyle(
        "FinancePlusLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=NAVY,
    )
    value_style = ParagraphStyle(
        "FinancePlusValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#202A33"),
    )
    table_header = ParagraphStyle(
        "FinancePlusTableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8.3,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    table_cell = ParagraphStyle(
        "FinancePlusTableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=8.1,
        textColor=colors.HexColor("#202A33"),
        alignment=TA_LEFT,
    )
    table_center = ParagraphStyle(
        "FinancePlusTableCenter",
        parent=table_cell,
        alignment=TA_CENTER,
    )

    client_name = _text(client.get("Cliente"), "Cliente")
    story = [
        Paragraph("FinancePlus — Riepilogo documentale", title_style),
        Paragraph(
            f"Cliente: <b>{escape(client_name)}</b> &nbsp;&nbsp; | &nbsp;&nbsp; "
            f"Generato il {date.today().strftime('%d/%m/%Y')}",
            subtitle_style,
        ),
    ]

    info_data = [
        [
            Paragraph("Partita IVA", label_style),
            Paragraph("Codice Fiscale", label_style),
            Paragraph("REA", label_style),
            Paragraph("Ultimo bilancio", label_style),
            Paragraph("Rating", label_style),
            Paragraph("Documenti", label_style),
        ],
        [
            _paragraph(client.get("Partita IVA"), value_style),
            _paragraph(client.get("Codice Fiscale"), value_style),
            _paragraph(client.get("REA"), value_style),
            _paragraph(client.get("Ultimo bilancio disponibile"), value_style),
            _paragraph(client.get("Rating FinancePlus"), value_style),
            Paragraph(str(len(summary)), value_style),
        ],
    ]
    info = Table(info_data, colWidths=[43 * mm, 43 * mm, 36 * mm, 36 * mm, 32 * mm, 25 * mm])
    info.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), LIGHT_COPPER),
                ("BACKGROUND", (0, 1), (-1, 1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([info, Spacer(1, 4 * mm)])

    if summary.empty:
        story.append(Paragraph("Nessun documento collegato al cliente.", value_style))
    else:
        type_counts = summary["Tipo"].value_counts().to_dict()
        breakdown = " · ".join(f"{escape(str(k))}: {v}" for k, v in type_counts.items())
        story.append(
            Paragraph(
                f"<b>Totale documenti:</b> {len(summary)}"
                + (f" &nbsp;&nbsp; | &nbsp;&nbsp; <b>Tipologie:</b> {breakdown}" if breakdown else ""),
                subtitle_style,
            )
        )

        headers = ["N.", "Tipo", "Esercizio", "Data", "Documento", "Pratica", "Origine", "Stato", "Drive"]
        table_data = [[Paragraph(escape(header), table_header) for header in headers]]

        for _, row in summary.iterrows():
            drive_url = row.get("Drive")
            if drive_url:
                safe_url = escape(str(drive_url), {'"': '&quot;'})
                drive_cell = Paragraph(f'<link href="{safe_url}" color="#0B5CAD"><u>Apri</u></link>', table_center)
            else:
                drive_cell = Paragraph("—", table_center)

            table_data.append(
                [
                    Paragraph(escape(str(row.get("N.", ""))), table_center),
                    Paragraph(escape(_text(row.get("Tipo"))), table_cell),
                    Paragraph(escape(_text(row.get("Esercizio"))), table_center),
                    Paragraph(escape(_text(row.get("Data"))), table_center),
                    Paragraph(escape(_text(row.get("Documento"))), table_cell),
                    Paragraph(escape(_text(row.get("Pratica"))), table_cell),
                    Paragraph(escape(_text(row.get("Origine"))), table_cell),
                    Paragraph(escape(_text(row.get("Stato"))), table_cell),
                    drive_cell,
                ]
            )

        widths = [8, 27, 18, 22, 86, 28, 24, 26, 18]
        table = LongTable(
            table_data,
            colWidths=[width * mm for width in widths],
            repeatRows=1,
            hAlign="LEFT",
        )
        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("BOX", (0, 0), (-1, -1), 0.55, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        for row_index in range(1, len(table_data)):
            if row_index % 2 == 0:
                style_commands.append(("BACKGROUND", (0, row_index), (-1, row_index), LIGHT_GRAY))
        table.setStyle(TableStyle(style_commands))
        story.append(table)

    story.extend(
        [
            Spacer(1, 4 * mm),
            Paragraph(
                "Il riepilogo riflette i record presenti nella tabella Documenti di Airtable al momento della generazione. "
                "I collegamenti Drive sono mostrati solo quando l'URL e disponibile nel record.",
                subtitle_style,
            ),
        ]
    )

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
