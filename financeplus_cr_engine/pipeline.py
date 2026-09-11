from pathlib import Path
import json
from .parser import parse_file
from .engine import analyze
from .pdf_generator import generate_pdf

def run(input_path, output_pdf, audit_json=None, allow_invalid=False):
    parsed=parse_file(input_path); analysis=analyze(parsed)
    if audit_json: Path(audit_json).write_text(json.dumps(analysis.to_dict(),ensure_ascii=False,indent=2),encoding='utf-8')
    generate_pdf(analysis,output_pdf,allow_invalid=allow_invalid)
    return analysis
