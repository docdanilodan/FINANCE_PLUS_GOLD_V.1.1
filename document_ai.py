from __future__ import annotations
import hashlib, re
from dataclasses import dataclass
from typing import Optional

@dataclass
class DocumentResult:
    category: str
    company_name: str = ""
    document_year: Optional[int] = None
    period: str = ""
    bank: str = ""
    number: str = ""
    confidence: float = 0.0

RULES = [
    ("Ricevuta deposito Bilancio d'esercizio", ["ricevuta dell'avvenuta presentazione", "presentazione via telematica", "deposito bilancio", "diritti di segreteria"]),
    ("Centrale Rischi Banca d'Italia", ["centrale dei rischi", "banca d'italia", "accordato", "utilizzato"]),
    ("Estratto conto", ["estratto conto", "saldo", "movimenti", "iban"]),
    ("Bilancio d'esercizio", ["bilancio", "stato patrimoniale", "conto economico"]),
    ("Visura Camerale", ["camera di commercio", "registro imprese", "visura"]),
    ("Contratto di finanziamento", ["contratto di finanziamento", "finanziatore", "mutuatario"]),
    ("Fattura", ["fattura", "imponibile", "iva"]),
    ("DURC", ["documento unico di regolarita contributiva", "durc"]),
    ("Preventivo", ["preventivo"]),
    ("Offerta", ["offerta"]),
    ("Curriculum Vitae", ["curriculum vitae", "esperienza professionale"]),
]

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def classify_text(text: str) -> DocumentResult:
    blob = re.sub(r"\s+", " ", (text or "").lower())
    best = ("Altro", 0)
    for category, markers in RULES:
        hits = sum(1 for m in markers if m in blob)
        if hits > best[1]: best = (category, hits)
    confidence = min(0.99, 0.55 + best[1] * 0.12) if best[1] else 0.25
    return DocumentResult(category=best[0], confidence=confidence)

def safe_piece(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|\r\n\t]+', ' ', value or '')
    return re.sub(r'\s+', ' ', value).strip(' ._')

def suggested_name(r: DocumentResult, extension: str = ".pdf") -> str:
    c = safe_piece(r.company_name) or "SOGGETTO DA VERIFICARE"
    y = f" {r.document_year}" if r.document_year else ""
    if r.category == "Visura Camerale": return f"{c}_Visura Camerale{extension}"
    if r.category == "Bilancio d'esercizio": return f"{c}_Bilancio d'esercizio{y}{extension}"
    if r.category == "Ricevuta deposito Bilancio d'esercizio": return f"{c}_Ricevuta deposito Bilancio d'esercizio{y}{extension}"
    if r.category == "Centrale Rischi Banca d'Italia": return f"{c}_Centrale Rischi Banca d'Italia {safe_piece(r.period)}{extension}".replace(f"  {extension}", extension)
    if r.category == "Estratto conto": return f"{c}_Estratto conto {safe_piece(r.period)} {safe_piece(r.bank)}{y}{extension}".replace('  ', ' ')
    if r.category == "Fattura": return f"{c}_Fattura N.{safe_piece(r.number)}{y}{extension}".replace('N. ', 'N.')
    if r.category == "Contratto di finanziamento": return f"{c}_Contratto di finanziamento {safe_piece(r.bank)}{y}{extension}".replace('  ', ' ')
    return f"{c}_{safe_piece(r.category)}{y}{extension}"
