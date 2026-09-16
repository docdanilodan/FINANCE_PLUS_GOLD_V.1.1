from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

@dataclass
class Provenance:
    source_chat: str = ""
    source_file: str = ""
    source_version: str = ""
    source_hash: str = ""

@dataclass
class Client:
    id: str | None = None
    legal_name: str = ""
    vat: str = ""
    tax_code: str = ""
    pec: str = ""
    rea: str = ""
    registered_office: str = ""
    postal_code: str = ""
    city: str = ""
    province: str = ""
    ateco: str = ""
    legal_form: str = ""
    administrator: str = ""
    share_capital: float | None = None
    notes: str = ""
    provenance: Provenance = field(default_factory=Provenance)

@dataclass
class Practice:
    id: str | None = None
    client_id: str = ""
    code: str = ""
    practice_type: str = ""
    institution: str = ""
    requested_amount: float | None = None
    status: str = "Da avviare"
    priority: str = "Media"
    owner: str = ""
    next_action: str = ""
    next_action_due: date | None = None
    missing_documents: str = ""
    documentation_status: str = "Da verificare"
    alerts: str = ""

@dataclass
class DocumentRecord:
    id: str | None = None
    client_id: str | None = None
    practice_id: str | None = None
    category: str = "Altro"
    original_name: str = ""
    canonical_name: str = ""
    sha256: str = ""
    storage_uri: str = ""
    source_channel: str = "manuale"
    source_message_id: str = ""
    verification_status: str = "DA_VERIFICARE"
    document_date: date | None = None
    fiscal_year: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: Provenance = field(default_factory=Provenance)

@dataclass
class CRMEvent:
    id: str | None = None
    client_id: str | None = None
    practice_id: str | None = None
    event_type: str = "Nota"
    event_at: datetime = field(default_factory=datetime.now)
    sender_role: str = ""
    sender_name: str = ""
    recipient_role: str = ""
    recipient_name: str = ""
    institution: str = ""
    amount: float | None = None
    instrument: str = ""
    subject: str = ""
    details: str = ""
    status: str = "INEVASA"

@dataclass
class AnalysisRecord:
    id: str | None = None
    client_id: str | None = None
    practice_id: str | None = None
    analysis_type: str = "credit"
    created_at: datetime = field(default_factory=datetime.now)
    data_quality: int = 0
    score: float | None = None
    rating: str = "INCOMPLETO"
    pd_label: str = "NON CALCOLATA"
    result_json: dict[str, Any] = field(default_factory=dict)

@dataclass
class MandateRecord:
    id: str | None = None
    client_id: str | None = None
    practice_id: str | None = None
    percentage: float = 0.0
    fixed_fee: float = 0.0
    basis_amount: float = 0.0
    notes: str = ""

@dataclass
class OperatorProfile:
    code: str
    name: str
    category: str
    active: bool = True
    weights: dict[str, float] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    required_documents: list[str] = field(default_factory=list)
    source: str = ""
