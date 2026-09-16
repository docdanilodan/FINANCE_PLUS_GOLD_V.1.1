from __future__ import annotations
from dataclasses import dataclass

@dataclass
class PhantomResult:
    status: str
    score: float | None
    rating: str
    pd_label: str
    components: dict[str, float]
    warnings: list[str]


def _rating(score: float) -> str:
    if score >= 97: return "AAA"
    if score >= 92: return "AA"
    if score >= 80: return "A"
    if score >= 60: return "BBB"
    if score >= 50: return "BB"
    if score >= 35: return "B"
    if score >= 20: return "CCC"
    return "D"

def compute_phantom(components: dict[str, float], *, weights: dict[str, float] | None = None, calibrated_pd: dict | None = None) -> PhantomResult:
    """PHANTOM shell.

    The recovered manuals confirm a 0-100 score/rating and an *indicative* PD, but the
    original scoring weights/calibration are not currently recoverable. Therefore the
    MASTER refuses to invent them: weights must be supplied from the recovered source or
    a separately approved calibrated ruleset.
    """
    if not weights:
        return PhantomResult("RICHIEDE_SORGENTE_ORIGINALE", None, "NON CALCOLATO", "PD NON CALCOLATA", components, ["Pesi PHANTOM originali non disponibili: nessun punteggio viene inventato."])
    missing = [k for k in weights if k not in components]
    if missing:
        return PhantomResult("INCOMPLETO", None, "NON CALCOLATO", "PD NON CALCOLATA", components, ["Componenti mancanti: " + ", ".join(missing)])
    total_weight = sum(float(v) for v in weights.values())
    if total_weight <= 0:
        return PhantomResult("ERRORE_RULESET", None, "NON CALCOLATO", "PD NON CALCOLATA", components, ["Somma pesi PHANTOM non valida."])
    score = sum(float(components[k]) * float(w) for k, w in weights.items()) / total_weight
    score = max(0.0, min(100.0, score))
    pd_label = "PD INDICATIVA - NON CALIBRATA"
    warnings = ["Il rating PHANTOM è simulativo e non sostituisce la delibera bancaria."]
    if calibrated_pd:
        pd_label = "PD CALIBRATA" if calibrated_pd.get("validated") else pd_label
    return PhantomResult("OK", round(score, 2), _rating(score), pd_label, components, warnings)
