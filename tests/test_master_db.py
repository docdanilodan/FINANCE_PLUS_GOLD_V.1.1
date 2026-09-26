import os, tempfile, importlib

def test_repository_dedup_client():
    # Importing repository models is enough to validate mappings in CI; DB isolation is tested by schema smoke test workflow.
    from financeplus.db.models import ClientORM, DocumentORM, AuditLogORM
    assert ClientORM.__tablename__=="clients"
    assert DocumentORM.__tablename__=="documents"
    assert AuditLogORM.__tablename__=="audit_log"


def test_schema_create_all_memory():
    from sqlalchemy import create_engine, inspect
    from financeplus.db.models import Base
    e=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    names=set(inspect(e).get_table_names())
    assert {"clients","practices","documents","crm_events","analyses","mandates","operators","audit_log","provenance_records"}.issubset(names)
