from __future__ import annotations
from datetime import datetime
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session
from .models import ClientORM, PracticeORM, DocumentORM, CRMEventORM, AnalysisORM, AuditLogORM, OperatorORM

class Repository:
    """Thin repository. Transaction boundaries are controlled by session_scope()."""
    def __init__(self, session: Session):
        self.s = session

    def counts(self) -> dict[str, int]:
        return {
            "clients": self.s.scalar(select(func.count(ClientORM.id))) or 0,
            "practices": self.s.scalar(select(func.count(PracticeORM.id))) or 0,
            "documents": self.s.scalar(select(func.count(DocumentORM.id))) or 0,
            "events": self.s.scalar(select(func.count(CRMEventORM.id))) or 0,
            "analyses": self.s.scalar(select(func.count(AnalysisORM.id))) or 0,
        }

    def list_clients(self, query: str = "", limit: int = 1000):
        stmt = select(ClientORM).order_by(ClientORM.legal_name).limit(limit)
        q = query.strip()
        if q:
            like = f"%{q}%"
            stmt = stmt.where(or_(ClientORM.legal_name.ilike(like), ClientORM.vat.ilike(like), ClientORM.tax_code.ilike(like), ClientORM.pec.ilike(like), ClientORM.rea.ilike(like)))
        return list(self.s.scalars(stmt))

    def create_client(self, **fields):
        vat = str(fields.get("vat") or "").strip()
        tax_code = str(fields.get("tax_code") or "").strip()
        legal_name = str(fields.get("legal_name") or "").strip()
        candidates = []
        if vat:
            candidates.append(ClientORM.vat == vat)
        if tax_code:
            candidates.append(ClientORM.tax_code == tax_code)
        if legal_name:
            candidates.append(func.lower(ClientORM.legal_name) == legal_name.lower())
        if candidates:
            existing = self.s.scalar(select(ClientORM).where(or_(*candidates)).limit(1))
            if existing:
                return existing, False
        if not legal_name:
            legal_name = f"CLIENTE DA COMPLETARE {datetime.utcnow():%Y-%m-%d %H:%M:%S}"
        obj = ClientORM(legal_name=legal_name, **{k:v for k,v in fields.items() if k != "legal_name"})
        self.s.add(obj); self.s.flush()
        return obj, True

    def create_practice(self, **fields):
        obj = PracticeORM(**fields); self.s.add(obj); self.s.flush(); return obj

    def list_practices(self, client_id: int | None = None):
        stmt = select(PracticeORM).order_by(PracticeORM.id.desc())
        if client_id is not None: stmt = stmt.where(PracticeORM.client_id == client_id)
        return list(self.s.scalars(stmt))

    def create_document(self, **fields):
        sha = fields.get("sha256")
        if sha:
            existing = self.s.scalar(select(DocumentORM).where(DocumentORM.sha256 == sha).limit(1))
            if existing: return existing, False
        obj = DocumentORM(**fields); self.s.add(obj); self.s.flush(); return obj, True

    def list_documents(self, client_id: int | None = None):
        stmt = select(DocumentORM).order_by(DocumentORM.created_at.desc())
        if client_id is not None: stmt = stmt.where(DocumentORM.client_id == client_id)
        return list(self.s.scalars(stmt))

    def create_event(self, **fields):
        obj = CRMEventORM(**fields); self.s.add(obj); self.s.flush(); return obj

    def list_events(self, client_id: int | None = None, limit: int = 500):
        stmt = select(CRMEventORM).order_by(CRMEventORM.event_at.desc()).limit(limit)
        if client_id is not None: stmt = stmt.where(CRMEventORM.client_id == client_id)
        return list(self.s.scalars(stmt))

    def create_analysis(self, **fields):
        obj = AnalysisORM(**fields); self.s.add(obj); self.s.flush(); return obj

    def list_operators(self):
        return list(self.s.scalars(select(OperatorORM).where(OperatorORM.active == 1).order_by(OperatorORM.name)))
