from __future__ import annotations

from datetime import datetime
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
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NAVY = colors.HexColor("#0B1F33")
COPPER = colors.HexColor("#B87333")
LIGHT_BLUE = colors.HexColor("#EEF3F7")
LIGHT_COPPER = colors.HexColor("#F5EEE8")
MID_GRAY = colors.HexColor("#6B7280")
BORDER = colors.HexColor("#D6DCE2")


def _missing(value: Any) -> bool:
    if value is None or value == "":
        return True
    try:
        result = pd.isna(value)
        return bool(result) if isinstance(result, bool) else False
    except Exception:
        return False


def _text(value: Any, default: str = "—") -> str:
    if _missing(value):
        return default
    text = str(value).strip()
    return text or default


def _date(value: Any) -> str:
    if _missing(value):
        return "—"
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return _text(value)
        return parsed.strftime("%d/%m/%Y")
    except Exception:
        return _text(value)


def _year(value: Any) -> str:
    if _missing(value):
        return "—"
    try:
        return str(int(float(value)))
    except Exception:
        return _text(value)


def _money(value: Any) -> str:
    if _missing(value):
        return "—"
    try:
        return f"€ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return _text(value)


def safe_fascicolo_filename(client_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(client_name or "Cliente")).strip("_")
    slug = slug[:90] or "Cliente"
    return f"F_P_GOLD_Fascicolo_Cliente_{slug}.pdf"


def _document_name(row: pd.Series) -> str:
    for field in ("Nome Definitivo", "Documento", "Nome IA Suggerito", "Nome Originale"):
        value = row.get(field)
        if not _missing(value) and str(value).strip():
            return str(value).strip()
    return "Documento senza nome"


def _footer(canvas, doc) -> None:
    canvas.saveState()
    width, _ = landscape(A4)
    canvas.setStrokeColor(COPPER)
    canvas.setLineWidth(0.7)
    canvas.line(14 * mm, 11 * mm, width - 14 * mm, 11 * mm)
    canvas.setFillColor(MID_GRAY)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(14 * mm, 6.8 * mm, "F_P_GOLD V_1.1 — Fascicolo Cliente")
    canvas.drawRightString(width - 14 * mm, 6.8 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


def build_client_fascicolo_pdf(
    client: Dict[str, Any],
    documents: pd.DataFrame,
    practices: pd.DataFrame,
    emails: pd.DataFrame,
    analyses: pd.DataFrame,
) -> bytes:
    buffer = BytesIO()
    client_name = _text(client.get("Cliente"), "Cliente")
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
        title=f"F_P_GOLD - Fascicolo Cliente - {client_name}",
        author="F_P_GOLD V_1.1",
        subject="Anagrafica, documenti, pratiche, email e analisi creditizie",
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle("FPTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=23, textColor=NAVY, alignment=TA_LEFT, spaceAfter=4 * mm)
    section = ParagraphStyle("FPSection", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=3 * mm)
    note = ParagraphStyle("FPNote", parent=styles["Normal"], fontName="Helvetica", fontSize=8.2, leading=10.5, textColor=MID_GRAY, spaceAfter=3 * mm)
    label = ParagraphStyle("FPLabel", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=NAVY)
    value = ParagraphStyle("FPValue", parent=styles["Normal"], fontName="Helvetica", fontSize=7.2, leading=9, textColor=colors.HexColor("#202A33"))
    th = ParagraphStyle("FPHeader", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=6.5, leading=7.7, textColor=colors.white, alignment=TA_CENTER)
    td = ParagraphStyle("FPBody", parent=styles["Normal"], fontName="Helvetica", fontSize=6.1, leading=7.4, textColor=colors.HexColor("#202A33"), alignment=TA_LEFT)
    tc = ParagraphStyle("FPCenter", parent=td, alignment=TA_CENTER)

    def p(value_in: Any, style: ParagraphStyle, limit: int | None = None) -> Paragraph:
        text = _text(value_in)
        if limit and len(text) > limit:
            text = text[: max(0, limit - 1)].rstrip() + "…"
        return Paragraph(escape(text), style)

    def styled_table(data, widths, header_rows: int = 0, header_color=NAVY, long: bool = False):
        cls = LongTable if long else Table
        table = cls(data, colWidths=[w * mm for w in widths], repeatRows=header_rows)
        commands = [
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        if header_rows:
            commands.append(("BACKGROUND", (0, 0), (-1, header_rows - 1), header_color))
        table.setStyle(TableStyle(commands))
        return table

    story = [
        Paragraph("F_P_GOLD V_1.1 — Fascicolo Cliente", title),
        Paragraph(f"Cliente: <b>{escape(client_name)}</b> &nbsp;&nbsp; | &nbsp;&nbsp; Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}", note),
    ]

    profile_rows = [
        ["Ragione sociale", client.get("Cliente"), "P.IVA", client.get("Partita IVA"), "Codice fiscale", client.get("Codice Fiscale")],
        ["PEC", client.get("PEC"), "Email", client.get("Email"), "REA", client.get("REA")],
        ["Sede legale", client.get("Sede legale"), "Comune / Provincia", f"{_text(client.get('Comune'))} / {_text(client.get('Provincia'))}", "CAP", client.get("CAP")],
        ["Forma giuridica", client.get("Forma giuridica"), "Stato attività", client.get("Stato attività"), "ATECO", client.get("ATECO")],
        ["Attività prevalente", client.get("Attività prevalente"), "Capitale sociale", _money(client.get("Capitale sociale EUR")), "Amministratore", client.get("Rappresentante/Amministratore")],
        ["Ultima visura", _date(client.get("Data estrazione visura")), "Ultimo bilancio", client.get("Ultimo bilancio disponibile"), "CR aggiornata al", _date(client.get("CR aggiornata al"))],
        ["Rating", client.get("Rating FinancePlus"), "Stato verifica", client.get("Stato verifica anagrafica"), "Stato cliente", client.get("Stato Cliente")],
    ]
    profile = []
    for row in profile_rows:
        profile.append([p(row[0], label), p(row[1], value, 220), p(row[2], label), p(row[3], value, 180), p(row[4], label), p(row[5], value, 180)])
    profile_table = Table(profile, colWidths=[26*mm, 58*mm, 27*mm, 48*mm, 29*mm, 58*mm])
    profile_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (0,-1), LIGHT_COPPER), ("BACKGROUND", (2,0), (2,-1), LIGHT_COPPER), ("BACKGROUND", (4,0), (4,-1), LIGHT_COPPER),
        ("BOX", (0,0), (-1,-1), 0.55, BORDER), ("INNERGRID", (0,0), (-1,-1), 0.3, BORDER), ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.extend([profile_table, Spacer(1, 4 * mm)])

    counts = [[p("Documenti", label), p(len(documents) if documents is not None else 0, value), p("Pratiche", label), p(len(practices) if practices is not None else 0, value), p("Email", label), p(len(emails) if emails is not None else 0, value), p("Analisi", label), p(len(analyses) if analyses is not None else 0, value)]]
    counts_table = Table(counts, colWidths=[25*mm,18*mm,23*mm,18*mm,20*mm,18*mm,22*mm,18*mm])
    counts_table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), LIGHT_BLUE), ("BOX", (0,0), (-1,-1), 0.55, BORDER), ("INNERGRID", (0,0), (-1,-1), 0.3, BORDER), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5), ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5)]))
    story.extend([counts_table, Spacer(1, 4 * mm)])

    if not _missing(client.get("Note")):
        story.extend([Paragraph("Note cliente", section), p(client.get("Note"), value, 1800), Spacer(1, 3 * mm)])

    docs = documents.copy() if documents is not None else pd.DataFrame()
    if not docs.empty:
        docs["_name"] = docs.apply(_document_name, axis=1)
        docs["_year"] = pd.to_numeric(docs.get("Esercizio"), errors="coerce")
        docs["_date"] = pd.to_datetime(docs.get("Data Documento"), errors="coerce")
        docs = docs.sort_values(["_year", "_date", "_name"], ascending=[False, False, True], na_position="last")

    story.append(Paragraph("Riepilogo documenti per categoria", section))
    if docs.empty:
        story.append(p("Nessun documento collegato.", value))
    else:
        categories = docs["Tipo Documento"].fillna("Non classificato").astype(str).replace("", "Non classificato").value_counts()
        cat_data = [[p("Tipologia", th), p("N.", th)]] + [[p(k, td), p(v, tc)] for k, v in categories.items()]
        story.append(styled_table(cat_data, [90, 20], 1))

    story.extend([PageBreak(), Paragraph("Pratiche e controllo dossier", section)])
    if practices is None or practices.empty:
        story.append(p("Nessuna pratica collegata.", value))
    else:
        p_headers = ["Pratica", "Tipo", "Istituto", "Importo", "Stato", "Priorità", "Responsabile", "Scadenza"]
        pdata = [[p(h, th) for h in p_headers]]
        for _, row in practices.iterrows():
            pdata.append([p(row.get("Pratica ID"), td), p(row.get("Tipo Pratica"), td), p(row.get("Istituto"), td), p(_money(row.get("Importo Richiesto")), td), p(row.get("Stato"), td), p(row.get("Priorità"), tc), p(row.get("Responsabile pratica"), td), p(_date(row.get("Scadenza")), tc)])
        story.extend([styled_table(pdata, [34,28,35,28,28,22,40,24], 1, long=True), Spacer(1, 4*mm)])

        c_headers = ["Pratica", "Stato documentazione", "Completezza", "Documenti mancanti", "Prossima azione", "Scadenza azione", "Alert / criticità"]
        cdata = [[p(h, th) for h in c_headers]]
        for _, row in practices.iterrows():
            cdata.append([p(row.get("Pratica ID"), td), p(row.get("Stato documentazione"), td), p(row.get("Completezza dossier"), tc), p(row.get("Documenti mancanti"), td, 650), p(row.get("Prossima azione"), td, 650), p(_date(row.get("Scadenza prossima azione")), tc), p(row.get("Alert e criticità"), td, 750)])
        story.append(styled_table(cdata, [31,31,24,55,55,28,55], 1, COPPER, True))

    story.extend([PageBreak(), Paragraph("Archivio documentale completo", section)])
    if docs.empty:
        story.append(p("Nessun documento collegato.", value))
    else:
        d_headers = ["N.", "Tipo", "Esercizio", "Data", "Documento", "Pratica", "Origine", "Stato", "Drive"]
        ddata = [[p(h, th) for h in d_headers]]
        for number, (_, row) in enumerate(docs.iterrows(), start=1):
            url = "" if _missing(row.get("URL Drive")) else str(row.get("URL Drive")).strip()
            drive = Paragraph(f'<link href="{escape(url, {chr(34): "&quot;"})}" color="#0B5CAD"><u>Apri</u></link>', tc) if url.startswith(("http://", "https://")) else p("—", tc)
            ddata.append([p(number, tc), p(row.get("Tipo Documento"), td), p(_year(row.get("Esercizio")), tc), p(_date(row.get("Data Documento")), tc), p(_document_name(row), td, 360), p(row.get("Pratica ID"), td), p(row.get("Origine"), td), p(row.get("Stato Verifica"), td), drive])
        story.append(styled_table(ddata, [8,27,18,22,86,28,24,26,18], 1, long=True))

    story.extend([PageBreak(), Paragraph("Email collegate", section)])
    if emails is None or emails.empty:
        story.append(p("Nessuna email collegata.", value))
    else:
        ework = emails.copy()
        ework["_sort"] = pd.to_datetime(ework.get("Data e ora"), errors="coerce")
        ework = ework.sort_values("_sort", ascending=False, na_position="last")
        e_headers = ["Data", "Mittente", "Oggetto", "Priorità", "Azione richiesta", "Allegati", "Gestita", "Sintesi IA"]
        edata = [[p(h, th) for h in e_headers]]
        for _, row in ework.iterrows():
            edata.append([p(_date(row.get("Data e ora")), tc), p(row.get("Mittente"), td, 200), p(row.get("Oggetto"), td, 280), p(row.get("Priorità"), tc), p(row.get("Azione Richiesta"), td, 500), p(row.get("Allegati"), td, 400), p(row.get("Gestita"), tc), p(row.get("Sintesi IA"), td, 900)])
        story.append(styled_table(edata, [24,36,55,21,48,42,20,58], 1, long=True))

    story.extend([PageBreak(), Paragraph("Analisi creditizie", section)])
    if analyses is None or analyses.empty:
        story.append(p("Nessuna analisi creditizia collegata.", value))
    else:
        awork = analyses.copy()
        awork["_sort"] = pd.to_datetime(awork.get("Data Analisi"), errors="coerce")
        awork = awork.sort_values("_sort", ascending=False, na_position="last")
        a_headers = ["Data", "Esercizio", "Ricavi", "EBITDA", "EBITDA %", "PFN", "PFN/EBITDA", "DSCR", "Score", "Rating", "Sostenibile min", "Sostenibile max"]
        adata = [[p(h, th) for h in a_headers]]
        for _, row in awork.iterrows():
            adata.append([p(_date(row.get("Data Analisi")), tc), p(_year(row.get("Esercizio")), tc), p(_money(row.get("Ricavi")), td), p(_money(row.get("EBITDA")), td), p(row.get("EBITDA Margin"), tc), p(_money(row.get("PFN")), td), p(row.get("PFN EBITDA"), tc), p(row.get("DSCR"), tc), p(row.get("Score"), tc), p(row.get("Rating"), tc), p(_money(row.get("Importo Sostenibile Min")), td), p(_money(row.get("Importo Sostenibile Max")), td)])
        story.extend([styled_table(adata, [23,18,27,27,20,27,24,19,18,18,31,31], 1, long=True), Spacer(1, 4*mm)])
        for _, row in awork.iterrows():
            story.append(Paragraph(f"<b>{escape('Analisi ' + _date(row.get('Data Analisi')) + ' — Rating ' + _text(row.get('Rating')))}</b>", note))
            details = [[p("Punti di forza", label), p(row.get("Punti di Forza"), value, 1400)], [p("Criticità", label), p(row.get("Criticità"), value, 1400)], [p("Raccomandazione IA", label), p(row.get("Raccomandazione IA"), value, 1600)]]
            detail_table = Table(details, colWidths=[38*mm,220*mm])
            detail_table.setStyle(TableStyle([("BACKGROUND", (0,0), (0,-1), LIGHT_COPPER), ("BOX", (0,0), (-1,-1), 0.45, BORDER), ("INNERGRID", (0,0), (-1,-1), 0.25, BORDER), ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4), ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4)]))
            story.extend([detail_table, Spacer(1, 3*mm)])

    story.extend([Spacer(1, 4*mm), Paragraph("Il Fascicolo Cliente riflette esclusivamente i dati presenti nelle tabelle Airtable collegate al momento della generazione. I campi mancanti restano indicati con — e non vengono ricostruiti o inventati.", note)])
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer.getvalue()
