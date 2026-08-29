from __future__ import annotations

import calendar
import hashlib
import re
from dataclasses import dataclass
from datetime import date
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
    reference_date: Optional[str] = None


# Specific categories come before generic ones.
RULES = [
    (
        "Ricevuta deposito Bilancio d'esercizio",
        [
            "ricevuta dell'avvenuta presentazione",
            "presentazione via telematica",
            "deposito bilancio",
            "diritti di segreteria",
        ],
    ),
    (
        "Bozza bilancio",
        [
            "bozza bilancio",
            "bozza di bilancio",
            "bilancio provvisorio",
            "provvisorio al",
            "bilancio di verifica",
        ],
    ),
    (
        "Bilancio analitico",
        [
            "bilancio analitico",
            "situazione contabile",
            "sezioni contrapposte",
            "conto economico analitico",
            "stato patrimoniale analitico",
            "bilancio dettagliato",
        ],
    ),
    (
        "Prospetto bilancio",
        [
            "prospetto di bilancio",
            "prospetto bilancio",
            "bilancio riclassificato",
            "riclassificato comparato",
        ],
    ),
    (
        "Presentazione aziendale",
        [
            "presentazione aziendale",
            "company profile",
            "pitch deck",
            "presentazione societa",
            "presentazione società",
        ],
    ),
    (
        "Centrale Rischi Banca d'Italia",
        ["centrale dei rischi", "centrale rischi", "banca d'italia", "accordato", "utilizzato"],
    ),
    ("Estratto conto", ["estratto conto", "rendiconto bancario", "conto scalare", "saldo", "movimenti", "iban"]),
    ("Bilancio d'esercizio", ["bilancio", "stato patrimoniale", "conto economico"]),
    ("Visura Camerale", ["camera di commercio", "registro imprese", "visura"]),
    ("Contratto di finanziamento", ["contratto di finanziamento", "finanziatore", "mutuatario"]),
    ("Fattura", ["fattura", "imponibile", "iva"]),
    ("DURC", ["documento unico di regolarita contributiva", "documento unico di regolarità contributiva", "durc"]),
    ("Preventivo", ["preventivo"]),
    ("Offerta", ["offerta"]),
    ("Curriculum Vitae", ["curriculum vitae", "esperienza professionale"]),
]

# Explicit/specialized document types must win over generic balance-sheet terms.
PRIORITY_THRESHOLDS = {
    "Ricevuta deposito Bilancio d'esercizio": 2,
    "Bozza bilancio": 1,
    "Bilancio analitico": 1,
    "Prospetto bilancio": 1,
    "Presentazione aziendale": 1,
    "Centrale Rischi Banca d'Italia": 2,
    "Estratto conto": 2,
}

MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

BANK_PATTERNS = [
    ("Intesa Sanpaolo", ("intesa sanpaolo",)),
    ("Fideuram", ("fideuram",)),
    ("UniCredit", ("unicredit",)),
    ("BPER", ("bper banca", "bper")),
    ("Banco BPM", ("banco bpm",)),
    ("Crédit Agricole", ("crédit agricole", "credit agricole")),
    ("Credem", ("credem", "credito emiliano")),
    ("MPS", ("monte dei paschi", "mps")),
    ("Banca Generali", ("banca generali",)),
    ("Banca Sella", ("banca sella",)),
    ("Banca Valsabbina", ("valsabbina",)),
    ("CiviBank", ("civibank", "banca di cividale")),
    ("BCC Roma", ("bcc roma", "credito cooperativo di roma")),
    ("Cherry Bank", ("cherry bank",)),
    ("Deutsche Bank", ("deutsche bank",)),
    ("illimity", ("illimity",)),
    ("Qonto", ("qonto",)),
    ("Revolut", ("revolut",)),
    ("N26", ("n26",)),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _valid_year(value: int) -> bool:
    return 1990 <= value <= date.today().year + 1


def _parse_iso_date(day: str, month: str, year: str) -> Optional[str]:
    try:
        d = date(int(year), int(month), int(day))
    except ValueError:
        return None
    return d.isoformat()


def _extract_year(blob: str, category: str) -> Optional[int]:
    if category == "Ricevuta deposito Bilancio d'esercizio":
        patterns = [
            r"(?:data\s+atto|esercizio|bilancio\s+(?:abbreviato\s+)?d['’]?esercizio)[^0-9]{0,35}(20\d{2})",
            r"31[./-]12[./-](20\d{2})",
        ]
    elif category in {"Bilancio d'esercizio", "Bozza bilancio", "Bilancio analitico", "Prospetto bilancio"}:
        patterns = [
            r"(?:esercizio|bilancio|situazione\s+contabile|provvisorio|riclassificato)[^0-9]{0,35}(20\d{2})",
            r"(?:al\s+)?(?:31[./-]12|30[./-]06|31[./-]03|31[./-]07|30[./-]09)[./-](20\d{2})",
        ]
    else:
        patterns = [r"(?:anno|esercizio|periodo|del|al)[^0-9]{0,20}(20\d{2})"]

    for pattern in patterns:
        match = re.search(pattern, blob)
        if match:
            year = int(match.group(1))
            if _valid_year(year):
                return year

    if category == "Ricevuta deposito Bilancio d'esercizio":
        return None

    years = [int(value) for value in re.findall(r"(?<!\d)(20\d{2})(?!\d)", blob)]
    years = [value for value in years if _valid_year(value)]
    return max(years) if years else None


def _extract_bank(blob: str) -> str:
    for canonical, aliases in BANK_PATTERNS:
        if any(alias in blob for alias in aliases):
            return canonical
    return ""


def _extract_month_year(blob: str) -> tuple[Optional[int], Optional[int]]:
    keyword_month = re.search(
        r"(?:mese|periodo|riferimento|centrale\s+rischi)[^\n]{0,60}?(0?[1-9]|1[0-2])[./-](20\d{2})",
        blob,
    )
    if keyword_month:
        return int(keyword_month.group(1)), int(keyword_month.group(2))

    for name, month in MONTHS.items():
        match = re.search(rf"(?:mese|periodo|riferimento)?[^\n]{{0,35}}\b{name}\b\s+(20\d{{2}})", blob)
        if match:
            return month, int(match.group(1))
    return None, None


def _extract_reference_date(blob: str, category: str) -> Optional[str]:
    if category == "Visura Camerale":
        match = re.search(
            r"(?:data\s+(?:di\s+)?estrazione|estratta?\s+il|estratto\s+dal\s+registro\s+imprese[^0-9]{0,40})"
            r"[^0-9]{0,12}(\d{1,2})[./-](\d{1,2})[./-](20\d{2})",
            blob,
        )
        if match:
            return _parse_iso_date(match.group(1), match.group(2), match.group(3))

    if category == "Centrale Rischi Banca d'Italia":
        month, year = _extract_month_year(blob)
        if month and year:
            last_day = calendar.monthrange(year, month)[1]
            return date(year, month, last_day).isoformat()

    if category == "Estratto conto":
        dates = re.findall(r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})", blob)
        parsed = [_parse_iso_date(day, month, year) for day, month, year in dates]
        parsed = [value for value in parsed if value]
        return max(parsed) if parsed else None

    if category in {"Bilancio d'esercizio", "Bozza bilancio", "Bilancio analitico", "Prospetto bilancio"}:
        match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})", blob)
        if match:
            return _parse_iso_date(match.group(1), match.group(2), match.group(3))
    return None


def _period_from_reference(category: str, reference_date: Optional[str], blob: str) -> str:
    if category == "Centrale Rischi Banca d'Italia":
        month, year = _extract_month_year(blob)
        if month and year:
            month_name = next((name for name, number in MONTHS.items() if number == month), str(month))
            return f"{month_name} {year}"
    if category == "Estratto conto" and reference_date:
        d = date.fromisoformat(reference_date)
        quarter = ((d.month - 1) // 3) + 1
        return f"{quarter}° trimestre"
    return ""


def _extract_invoice_number(blob: str) -> str:
    match = re.search(r"fattura\s+(?:n\.?|numero)?\s*[:#-]?\s*([a-z0-9./_-]{1,30})", blob)
    return match.group(1).strip() if match else ""


def _enrich(result: DocumentResult, blob: str) -> DocumentResult:
    result.document_year = _extract_year(blob, result.category)
    result.reference_date = _extract_reference_date(blob, result.category)
    result.period = _period_from_reference(result.category, result.reference_date, blob)
    if result.category in {"Estratto conto", "Contratto di finanziamento"}:
        result.bank = _extract_bank(blob)
    if result.category == "Fattura":
        result.number = _extract_invoice_number(blob)
    if result.document_year is None and result.reference_date:
        result.document_year = int(result.reference_date[:4])
    return result


def classify_text(text: str) -> DocumentResult:
    blob = re.sub(r"\s+", " ", (text or "").lower())

    # First pass: honor the strong semantic identity of specialized documents.
    for category, markers in RULES:
        threshold = PRIORITY_THRESHOLDS.get(category)
        if threshold is None:
            continue
        hits = sum(1 for marker in markers if marker in blob)
        if category == "Estratto conto" and ("estratto conto" in blob or "rendiconto bancario" in blob or "conto scalare" in blob):
            hits = max(hits, threshold)
        if hits >= threshold:
            confidence = min(0.99, 0.62 + hits * 0.10)
            return _enrich(DocumentResult(category=category, confidence=confidence), blob)

    # Second pass: use ordinary marker scoring for the remaining categories.
    best_category = "Altro"
    best_hits = 0
    best_index = len(RULES)
    for index, (category, markers) in enumerate(RULES):
        hits = sum(1 for marker in markers if marker in blob)
        if hits > best_hits or (hits and hits == best_hits and index < best_index):
            best_category = category
            best_hits = hits
            best_index = index
    confidence = min(0.99, 0.55 + best_hits * 0.12) if best_hits else 0.25
    return _enrich(DocumentResult(category=best_category, confidence=confidence), blob)


def safe_piece(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|\r\n\t]+', ' ', value or '')
    return re.sub(r'\s+', ' ', value).strip(' ._')


def suggested_name(r: DocumentResult, extension: str = ".pdf") -> str:
    c = safe_piece(r.company_name) or "SOGGETTO DA VERIFICARE"
    y = f" {r.document_year}" if r.document_year else ""
    if r.category == "Visura Camerale":
        return f"{c}_Visura Camerale{extension}"
    if r.category == "Bilancio d'esercizio":
        return f"{c}_Bilancio d'esercizio{y}{extension}"
    if r.category == "Bozza bilancio":
        return f"{c}_Bozza bilancio{y}{extension}"
    if r.category == "Bilancio analitico":
        return f"{c}_Bilancio analitico{y}{extension}"
    if r.category == "Prospetto bilancio":
        return f"{c}_Prospetto bilancio{y}{extension}"
    if r.category == "Presentazione aziendale":
        return f"{c}_Presentazione aziendale{y}{extension}"
    if r.category == "Ricevuta deposito Bilancio d'esercizio":
        return f"{c}_Ricevuta deposito Bilancio d'esercizio{y}{extension}"
    if r.category == "Centrale Rischi Banca d'Italia":
        return f"{c}_Centrale Rischi Banca d'Italia {safe_piece(r.period)}{extension}".replace(f"  {extension}", extension)
    if r.category == "Estratto conto":
        return f"{c}_Estratto conto {safe_piece(r.period)} {safe_piece(r.bank)}{y}{extension}".replace('  ', ' ')
    if r.category == "Fattura":
        return f"{c}_Fattura N.{safe_piece(r.number)}{y}{extension}".replace('N. ', 'N.')
    if r.category == "Contratto di finanziamento":
        return f"{c}_Contratto di finanziamento {safe_piece(r.bank)}{y}{extension}".replace('  ', ' ')
    return f"{c}_{safe_piece(r.category)}{y}{extension}"
