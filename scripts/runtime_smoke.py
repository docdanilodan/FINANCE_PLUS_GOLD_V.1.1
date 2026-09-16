from __future__ import annotations

from sqlalchemy import inspect, text

from financeplus.db.session import engine, session_scope
from financeplus.db.repositories import Repository

EXPECTED_TABLES = {
    "clients",
    "practices",
    "documents",
    "crm_events",
    "analyses",
    "mandates",
    "operators",
    "audit_log",
    "provenance_records",
}


def main() -> None:
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar_one() == 1
    existing = set(inspect(engine).get_table_names())
    missing = sorted(EXPECTED_TABLES - existing)
    if missing:
        raise RuntimeError(f"MASTER schema missing tables: {missing}")
    with session_scope() as session:
        counts = Repository(session).counts()
    expected_count_keys = {"clients", "practices", "documents", "events", "analyses"}
    if set(counts) != expected_count_keys:
        raise RuntimeError(f"Unexpected repository counts payload: {counts}")
    print("FINANCEPLUS_RUNTIME_SMOKE_OK", counts, flush=True)


if __name__ == "__main__":
    main()
