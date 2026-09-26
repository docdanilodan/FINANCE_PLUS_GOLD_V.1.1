from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass
class MCCResult:
    status: str
    score: float | None
    areas: dict[str, float | None]
    ruleset_version: str
    warnings: list[str]


def evaluate_mcc(inputs: dict[str, Any], *, ruleset: dict | None = None) -> MCCResult:
    """Versioned MCC engine. No statutory/official rule is hard-coded without an approved ruleset."""
    if not ruleset:
        return MCCResult("RICHIEDE_RULESET", None, {"eco_fin": None, "cr": None, "cashflow": None}, "", ["Regole MCC complete non recuperate: modulo predisposto ma calcolo bloccato."])
    version = str(ruleset.get("version") or "unknown")
    area_cfg = ruleset.get("areas") or {}
    weights = ruleset.get("weights") or {}
    area_scores: dict[str, float | None] = {}
    warnings: list[str] = []
    for area in ("eco_fin", "cr", "cashflow"):
        cfg = area_cfg.get(area)
        if not cfg:
            area_scores[area] = None; warnings.append(f"Ruleset area {area} mancante."); continue
        required = cfg.get("required", [])
        if any(inputs.get(k) is None for k in required):
            area_scores[area] = None; warnings.append(f"Input mancanti area {area}."); continue
        formula = cfg.get("linear") or {}
        value = float(formula.get("intercept", 0.0)) + sum(float(formula.get(k, 0.0)) * float(inputs[k]) for k in required)
        area_scores[area] = max(0.0, min(100.0, value))
    if any(v is None for v in area_scores.values()):
        return MCCResult("INCOMPLETO", None, area_scores, version, warnings)
    tw = sum(float(weights.get(a, 0.0)) for a in area_scores)
    if tw <= 0: return MCCResult("ERRORE_RULESET", None, area_scores, version, warnings + ["Pesi MCC non validi."])
    score = sum(float(area_scores[a]) * float(weights.get(a, 0.0)) for a in area_scores) / tw
    return MCCResult("OK", round(score, 2), area_scores, version, warnings)
