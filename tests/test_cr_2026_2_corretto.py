from pathlib import Path
from pypdf import PdfReader
from financeplus_cr_engine import parse_text, analyze, generate_pdf

def sample():
    return '''Denominazione: TEST SRL\nCodice fiscale: 12345678901\nGennaio 2026\nRischi a revoca\nBANCA TEST SPA\nAccordato operativo: 100.000 Utilizzato: 75.000 Sconfinamento: 0\nFebbraio 2026\nRischi a revoca\nBANCA TEST SPA\nAccordato operativo: 100.000 Utilizzato: 80.000 Sconfinamento: 2.000\n'''

def test_parse_analyze_audit():
    p=parse_text(sample()); a=analyze(p)
    assert p.rows
    assert a.periods==['01/2026','02/2026']
    assert a.audit.valid
    assert a.score==88
    assert a.rating=='AA'
    assert 'Sconfini rilevati' in a.anomalies

def test_pdf_is_45_pages(tmp_path):
    a=analyze(parse_text(sample())); out=tmp_path/'cr.pdf'; generate_pdf(a,out)
    assert out.exists() and out.stat().st_size>10000
    assert len(PdfReader(str(out)).pages)==45

def test_invalid_blocks_pdf(tmp_path):
    a=analyze(parse_text('Denominazione: TEST SRL'))
    assert not a.audit.valid
    try: generate_pdf(a,tmp_path/'bad.pdf')
    except ValueError: pass
    else: raise AssertionError('PDF must be blocked when audit is invalid')
