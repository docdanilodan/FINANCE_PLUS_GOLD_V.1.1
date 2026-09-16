from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from financeplus.engines.cashflow.core import parse_statement, normalize_transactions
from financeplus_cr_engine.parser import parse_file
from financeplus_cr_engine.engine import analyze
from financeplus_cr_engine.pdf_generator import generate_pdf


def _statement_pdf() -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica", 8)
    c.drawString(40, 780, "DATA OPERAZIONE")
    c.drawString(150, 780, "DATA VALUTA")
    c.drawString(260, 780, "MOVIMENTI DARE")
    c.drawString(360, 780, "MOVIMENTI AVERE")
    c.drawString(460, 780, "DESCRIZIONE")
    c.drawString(40, 755, "02.01.2026")
    c.drawString(150, 755, "02.01.2026")
    c.drawString(300, 755, "100,00")
    c.drawString(460, 755, "PAGAMENTO TEST")
    c.drawString(40, 730, "03.01.2026")
    c.drawString(150, 730, "03.01.2026")
    c.drawString(400, 730, "250,00")
    c.drawString(460, 730, "BONIFICO TEST")
    c.save()
    return buf.getvalue()


def _cr_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    # Real prospect-like page.
    c.drawString(40, 800, "INFORMAZIONI PRESENTI NELL'ARCHIVIO DELLA CENTRALE DEI RISCHI")
    c.drawString(40, 782, "Date richieste: gen-26 dic-25")
    c.drawString(40, 764, "Intestatario: TEST INDUSTRIA S.R.L.")
    c.drawString(40, 746, "Codice fiscale: 12345678901")
    c.drawString(250, 710, "DATA DI RIFERIMENTO: gennaio 2026")
    c.drawString(40, 680, "Intermediario: BANCA TEST SPA")
    c.drawString(40, 650, "Crediti per cassa")
    c.drawString(40, 625, "Situazione corrente")
    c.drawString(40, 600, "RISCHI A SCADENZA")
    # Six monetary columns in the right half, matching the official prospect geometry.
    c.setFont("Helvetica", 6)
    for x, value in zip((350, 390, 430, 470, 510, 550), ("0", "100.000", "100.000", "80.000", "0", "0")):
        c.drawString(x, 575, value)
    c.setFont("Helvetica", 8)
    c.showPage()
    # Appended official guide: must never contaminate client observations.
    c.drawString(40, 800, "Il prospetto dati della Centrale dei rischi: guida alla lettura")
    c.drawString(40, 760, "DATA DI RIFERIMENTO: novembre 2010")
    c.drawString(40, 730, "Intermediario: BANCA ESEMPIO SPA")
    c.drawString(40, 700, "RISCHI A REVOCA")
    c.setFont("Helvetica", 6)
    for x, value in zip((350, 390, 430, 470, 510, 550), ("0", "999.000", "999.000", "999.000", "0", "0")):
        c.drawString(x, 675, value)
    c.save()


def test_cashflow_pdf_column_signs_are_preserved():
    raw = parse_statement("statement.pdf", _statement_pdf())
    tx = normalize_transactions(raw)
    assert len(tx) == 2
    assert sorted(round(v, 2) for v in tx["amount"].tolist()) == [-100.0, 250.0]


def test_cr_parser_stops_before_official_reading_guide(tmp_path: Path):
    src = tmp_path / "cr.pdf"
    _cr_pdf(src)
    parsed = parse_file(src)
    assert parsed.subject == "TEST INDUSTRIA S.R.L."
    assert parsed.periods == ["12/2025", "01/2026"]
    assert len(parsed.rows) == 1
    assert parsed.rows[0].period == "01/2026"
    assert parsed.rows[0].intermediary == "BANCA TEST SPA"
    assert parsed.rows[0].operating_accorded == 100000
    assert parsed.rows[0].used == 80000
    assert all(r.period != "11/2010" for r in parsed.rows)


def test_cr_pdf_output_is_readable(tmp_path: Path):
    src = tmp_path / "cr.pdf"
    out = tmp_path / "report.pdf"
    _cr_pdf(src)
    analysis = analyze(parse_file(src))
    generate_pdf(analysis, out)
    from pypdf import PdfReader
    reader = PdfReader(str(out))
    # Canonical historical generator parity: 45-page professional CR report.
    assert len(reader.pages) == 45
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    # The canonical report brands itself through title + financeplus.tech footer;
    # do not require a non-existent contiguous uppercase FINANCEPLUS token.
    assert "ANALISI" in text and "CR" in text and "AVANZATA" in text
    assert "www.financeplus.tech" in text
    assert "TEST INDUSTRIA S.R.L." in text
