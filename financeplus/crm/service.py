from __future__ import annotations
from financeplus.db.models import CRMEventORM

def create_event(session, **fields):
    obj=CRMEventORM(**fields); session.add(obj); session.flush(); return obj

def calendar_rows(events):
    return [{"date":e.event_at.date().isoformat(),"time":e.event_at.time().strftime("%H:%M"),"type":e.event_type,"client_id":e.client_id,"institution":e.institution,"subject":e.subject,"status":e.status} for e in events]
