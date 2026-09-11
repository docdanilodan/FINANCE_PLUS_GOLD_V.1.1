from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict


@dataclass
class CRRow:
    period: str
    intermediary: str
    category: str = "non classificata"
    technical_form: str = "non classificata"
    accorded: float = 0.0
    operating_accorded: float = 0.0
    used: float = 0.0
    guaranteed: float = 0.0
    overrun: float = 0.0
    source_page: int = 0
    raw: str = ""


@dataclass
class Guarantee:
    period: str
    intermediary: str
    guarantor: str
    value: float = 0.0
    guaranteed_amount: float = 0.0
    joint: bool = False
    source_page: int = 0


@dataclass
class InfoRequest:
    intermediary: str
    request_date: str = ""
    requested_period: str = ""
    request_type: str = "prima informazione"
    reason: str = ""
    source_page: int = 0


@dataclass
class Correction:
    period: str
    intermediary: str
    description: str
    source_page: int = 0


@dataclass
class ParsedCR:
    subject: str = "SOGGETTO NON RILEVATO"
    tax_code: str = ""
    periods: List[str] = field(default_factory=list)
    rows: List[CRRow] = field(default_factory=list)
    guarantees: List[Guarantee] = field(default_factory=list)
    info_requests: List[InfoRequest] = field(default_factory=list)
    corrections: List[Correction] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_name: str = ""


@dataclass
class AuditResult:
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class Analysis:
    subject: str
    tax_code: str
    periods: List[str]
    monthly: List[Dict]
    bank_ranking: Dict[str, List[Dict]]
    score: int
    rating: str
    pd: float
    anomalies: List[str]
    audit: AuditResult
    guarantees: List[Dict]
    info_requests: List[Dict]
    corrections: List[Dict]

    def to_dict(self):
        return asdict(self)
