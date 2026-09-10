from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


PHOTON_CATEGORIES = {
    "Fattura": "invoice",
    "Estratto conto": "statement",
    "Ricevuta": "receipt",
    "Remittance": "remittance",
    "Bill of Lading": "bol",
    "Fattura trasporto": "invoice-freight",
    "Fattura commerciale": "invoice-commercial",
}

FINANCEPLUS_ONLY_CATEGORIES = {
    "Visura Camerale",
    "Centrale Rischi Banca d'Italia",
    "Bilancio d'esercizio",
    "Bozza bilancio",
    "Bilancio analitico",
    "Prospetto bilancio",
    "Ricevuta deposito Bilancio d'esercizio",
    "Contratto di finanziamento",
    "Presentazione aziendale",
    "DURC",
    "Preventivo",
    "Offerta",
    "Curriculum Vitae",
}


@dataclass(frozen=True)
class RouteDecision:
    primary_engine: str
    secondary_engine: str = ""
    photon_doctype: str = ""
    needs_cross_check: bool = False
    needs_human_review: bool = False
    reason: str = ""
    confidence: float = 0.0
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def engine_label(self) -> str:
        if self.secondary_engine:
            return f"{self.primary_engine} + {self.secondary_engine}"
        return self.primary_engine


def decide_route(
    category: str,
    confidence: float,
    *,
    photon_configured: bool,
    photon_budget_remaining: int | None = None,
    low_confidence: float = 0.80,
    cross_check_confidence: float = 0.95,
) -> RouteDecision:
    """Choose the extraction engine without asking the operator.

    Routing policy:
    - specialist FinancePlus documents stay local;
    - Photon-supported documents use Photon when configured;
    - 0.80-0.95 confidence triggers a second-engine cross-check when possible;
    - <0.80 always requires review and, when possible, dual extraction;
    - if Photon is unavailable or its explicit budget is exhausted, fall back safely.
    """
    category = str(category or "Altro").strip()
    confidence = max(0.0, min(1.0, float(confidence or 0.0)))
    warnings: list[str] = []

    photon_available = photon_configured
    if photon_budget_remaining is not None and photon_budget_remaining <= 0:
        photon_available = False
        warnings.append("Budget Photon esaurito: fallback FinancePlus.")

    if category in FINANCEPLUS_ONLY_CATEGORIES:
        needs_review = confidence < low_confidence
        return RouteDecision(
            primary_engine="FinancePlus",
            needs_human_review=needs_review,
            reason="Documento specialistico gestito dal motore FinancePlus.",
            confidence=confidence,
            warnings=tuple(warnings),
        )

    photon_doctype = PHOTON_CATEGORIES.get(category, "")
    if photon_doctype:
        if not photon_available:
            warnings.append("Photon non configurato o non disponibile: uso FinancePlus.")
            return RouteDecision(
                primary_engine="FinancePlus",
                photon_doctype=photon_doctype,
                needs_human_review=confidence < cross_check_confidence,
                reason="Categoria compatibile con Photon, ma Photon non e disponibile.",
                confidence=confidence,
                warnings=tuple(warnings),
            )

        if confidence < low_confidence:
            return RouteDecision(
                primary_engine="Photon",
                secondary_engine="FinancePlus",
                photon_doctype=photon_doctype,
                needs_cross_check=True,
                needs_human_review=True,
                reason="Confidenza bassa: doppia estrazione e revisione.",
                confidence=confidence,
                warnings=tuple(warnings),
            )

        if confidence < cross_check_confidence:
            return RouteDecision(
                primary_engine="Photon",
                secondary_engine="FinancePlus",
                photon_doctype=photon_doctype,
                needs_cross_check=True,
                reason="Confidenza intermedia: Photon con controllo FinancePlus.",
                confidence=confidence,
                warnings=tuple(warnings),
            )

        return RouteDecision(
            primary_engine="Photon",
            secondary_engine="FinancePlus" if category in {"Fattura", "Estratto conto"} else "",
            photon_doctype=photon_doctype,
            needs_cross_check=category in {"Fattura", "Estratto conto"},
            reason="Categoria supportata da Photon; FinancePlus mantiene il Data Quality Gate.",
            confidence=confidence,
            warnings=tuple(warnings),
        )

    return RouteDecision(
        primary_engine="FinancePlus",
        needs_human_review=confidence < cross_check_confidence,
        reason="Tipo non mappato: FinancePlus prima, senza consumo Photon automatico.",
        confidence=confidence,
        warnings=tuple(warnings),
    )


def invoice_quality_gate(photon: dict, source_text: str = "") -> tuple[bool, list[str]]:
    """Deterministic checks for Photon invoice output."""
    issues: list[str] = []

    def num(key: str) -> float | None:
        value = photon.get(key)
        try:
            return None if value in (None, "") else float(value)
        except (TypeError, ValueError):
            issues.append(f"{key} non numerico")
            return None

    total = num("Total")
    subtotal = num("Subtotal")
    tax = num("Tax")
    shipping = num("Shipping") or 0.0
    discount = num("Discount") or 0.0

    if total is not None and subtotal is not None and tax is not None:
        expected = subtotal + tax + shipping - discount
        tolerance = max(0.02, abs(total) * 0.0005)
        if abs(expected - total) > tolerance:
            issues.append(
                f"Quadratura non valida: subtotal+tax+shipping-discount={expected:.2f}, total={total:.2f}"
            )

    items = photon.get("Line_Items") or []
    if isinstance(items, list) and items and total is not None:
        line_sum = 0.0
        valid = True
        for item in items:
            try:
                line_sum += float((item or {}).get("Amount") or 0.0)
            except (TypeError, ValueError):
                valid = False
        if valid and subtotal is not None:
            tolerance = max(0.02, abs(subtotal) * 0.0005)
            if abs(line_sum - subtotal) > tolerance:
                issues.append(f"Somma righe {line_sum:.2f} diversa dal subtotale {subtotal:.2f}")
        if valid and tax is not None:
            expected_from_lines = line_sum + tax + shipping - discount
            tolerance = max(0.02, abs(total) * 0.0005)
            if abs(expected_from_lines - total) > tolerance:
                issues.append(
                    f"Quadratura righe non valida: righe+tax+shipping-discount={expected_from_lines:.2f}, total={total:.2f}"
                )

    photon_date = str(photon.get("Date") or "").strip()
    if photon_date and source_text:
        try:
            y, m, d = photon_date.split("-")
            italian = f"{int(d):02d}/{int(m):02d}/{y}"
            inverted = f"{int(m):02d}/{int(d):02d}/{y}"
            normalized = source_text.replace("-", "/").replace(".", "/")
            if inverted in normalized and italian not in normalized and d != m:
                issues.append(
                    f"Possibile inversione giorno/mese: Photon {photon_date}, fonte contiene {inverted}"
                )
        except (ValueError, TypeError):
            issues.append(f"Data Photon non normalizzata: {photon_date}")

    return not issues, issues


def combine_review_flags(*issue_groups: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for group in issue_groups:
        for issue in group:
            text = str(issue).strip()
            if text and text not in seen:
                seen.add(text)
                out.append(text)
    return out
