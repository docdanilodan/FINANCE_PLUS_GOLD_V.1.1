from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Text, Float, Date, DateTime, ForeignKey, Integer, JSON, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class ClientORM(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vat: Mapped[str] = mapped_column(String(32), default="", index=True)
    tax_code: Mapped[str] = mapped_column(String(32), default="", index=True)
    pec: Mapped[str] = mapped_column(String(255), default="")
    rea: Mapped[str] = mapped_column(String(64), default="")
    registered_office: Mapped[str] = mapped_column(Text, default="")
    postal_code: Mapped[str] = mapped_column(String(16), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    province: Mapped[str] = mapped_column(String(16), default="")
    ateco: Mapped[str] = mapped_column(String(32), default="")
    legal_form: Mapped[str] = mapped_column(String(120), default="")
    administrator: Mapped[str] = mapped_column(String(255), default="")
    share_capital: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    practices = relationship("PracticeORM", back_populates="client", cascade="all, delete-orphan")
    documents = relationship("DocumentORM", back_populates="client")
    events = relationship("CRMEventORM", back_populates="client")
    __table_args__ = (
        Index("ix_clients_vat_nonblank", "vat"),
        Index("ix_clients_tax_code_nonblank", "tax_code"),
    )

class PracticeORM(Base):
    __tablename__ = "practices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    practice_type: Mapped[str] = mapped_column(String(80), default="")
    institution: Mapped[str] = mapped_column(String(255), default="")
    requested_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="Da avviare")
    priority: Mapped[str] = mapped_column(String(32), default="Media")
    owner: Mapped[str] = mapped_column(String(255), default="")
    next_action: Mapped[str] = mapped_column(Text, default="")
    next_action_due: Mapped[object | None] = mapped_column(Date, nullable=True)
    missing_documents: Mapped[str] = mapped_column(Text, default="")
    documentation_status: Mapped[str] = mapped_column(String(80), default="Da verificare")
    alerts: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    client = relationship("ClientORM", back_populates="practices")

class DocumentORM(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    practice_id: Mapped[int | None] = mapped_column(ForeignKey("practices.id", ondelete="SET NULL"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(120), default="Altro", index=True)
    original_name: Mapped[str] = mapped_column(String(500), default="")
    canonical_name: Mapped[str] = mapped_column(String(500), default="")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    storage_uri: Mapped[str] = mapped_column(Text, default="")
    source_channel: Mapped[str] = mapped_column(String(120), default="manuale")
    source_message_id: Mapped[str] = mapped_column(String(255), default="")
    verification_status: Mapped[str] = mapped_column(String(64), default="DA_VERIFICARE")
    document_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    client = relationship("ClientORM", back_populates="documents")

class CRMEventORM(Base):
    __tablename__ = "crm_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    practice_id: Mapped[int | None] = mapped_column(ForeignKey("practices.id", ondelete="SET NULL"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="Nota")
    event_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    sender_role: Mapped[str] = mapped_column(String(64), default="")
    sender_name: Mapped[str] = mapped_column(String(255), default="")
    recipient_role: Mapped[str] = mapped_column(String(64), default="")
    recipient_name: Mapped[str] = mapped_column(String(255), default="")
    institution: Mapped[str] = mapped_column(String(255), default="")
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    instrument: Mapped[str] = mapped_column(String(64), default="")
    subject: Mapped[str] = mapped_column(String(255), default="")
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(64), default="INEVASA")
    client = relationship("ClientORM", back_populates="events")

class AnalysisORM(Base):
    __tablename__ = "analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True, index=True)
    practice_id: Mapped[int | None] = mapped_column(ForeignKey("practices.id", ondelete="SET NULL"), nullable=True, index=True)
    analysis_type: Mapped[str] = mapped_column(String(80), default="credit")
    data_quality: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rating: Mapped[str] = mapped_column(String(32), default="INCOMPLETO")
    pd_label: Mapped[str] = mapped_column(String(120), default="NON CALCOLATA")
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class MandateORM(Base):
    __tablename__ = "mandates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), nullable=True)
    practice_id: Mapped[int | None] = mapped_column(ForeignKey("practices.id", ondelete="SET NULL"), nullable=True)
    percentage: Mapped[float] = mapped_column(Float, default=0.0)
    fixed_fee: Mapped[float] = mapped_column(Float, default=0.0)
    basis_amount: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class OperatorORM(Base):
    __tablename__ = "operators"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(120), default="")
    active: Mapped[int] = mapped_column(Integer, default=1)
    weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    constraints_json: Mapped[dict] = mapped_column(JSON, default=dict)
    required_documents_json: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(Text, default="")

class AuditLogORM(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(255), default="system")
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), default="")
    entity_id: Mapped[str] = mapped_column(String(120), default="")
    source: Mapped[str] = mapped_column(String(255), default="")
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)

class ProvenanceORM(Base):
    __tablename__ = "provenance_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feature: Mapped[str] = mapped_column(String(160), index=True)
    source_chat: Mapped[str] = mapped_column(String(255), default="")
    source_file: Mapped[str] = mapped_column(String(500), default="")
    source_version: Mapped[str] = mapped_column(String(120), default="")
    source_hash: Mapped[str] = mapped_column(String(128), default="")
    master_path: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(120), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("feature", "source_file", "source_version", name="uq_provenance_feature_source"),)
