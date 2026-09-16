from __future__ import annotations
from financeplus.db.models import AuditLogORM

def audit(session, action: str, *, actor: str = "system", entity_type: str = "", entity_id: str = "", source: str = "MASTER", detail: dict | None = None):
    row = AuditLogORM(actor=actor or "system", action=action, entity_type=entity_type, entity_id=str(entity_id or ""), source=source, detail_json=detail or {})
    session.add(row)
    session.flush()
    return row
