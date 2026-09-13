from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
import streamlit as st

APP_VERSION = "1.0.0-rc3-7c"
REQUIRED_TABLES = {
    "clients", "practices", "documents", "financials",
    "analyses", "mandates", "audit_events", "users",
}


def log(message: str) -> None:
    print(message, flush=True)


def connect():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL non configurato")
    return psycopg.connect(url, row_factory=dict_row)


def schema_check() -> tuple[bool, list[str]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        ).fetchall()
    names = [r["table_name"] for r in rows]
    return REQUIRED_TABLES.issubset(set(names)), names


def transactional_e2e() -> dict:
    marker = f"F7D{secrets.token_hex(5).upper()}"[:16]
    sha = hashlib.sha256(marker.encode("utf-8")).hexdigest()
    ids: dict[str, int] = {}

    conn = connect()
    try:
        client = conn.execute(
            "INSERT INTO clients(denom,piva) VALUES(%s,%s) RETURNING id",
            ("PLUGIN TOP_00 FASE7D STREAMLIT E2E", marker),
        ).fetchone()
        ids["client_id"] = int(client["id"])

        practice = conn.execute(
            "INSERT INTO practices(client_id,status,product,amount,duration,purpose,owner) "
            "VALUES(%s,'NUOVA','TEST_STREAMLIT',12345.67,12,'FASE 7D Streamlit E2E','streamlit') RETURNING id",
            (ids["client_id"],),
        ).fetchone()
        ids["practice_id"] = int(practice["id"])

        document = conn.execute(
            "INSERT INTO documents(client_id,practice_id,category,filename,storage_url,sha256,engine,engine_version,confidence,verification_state,source_id) "
            "VALUES(%s,%s,'Report PDF','FASE7D_STREAMLIT.txt','memory://fase7d',%s,'FASE7D','1.0.0-rc3-7c',1.0,'SMOKE_TEST','streamlit-7d') RETURNING id",
            (ids["client_id"], ids["practice_id"], sha),
        ).fetchone()
        ids["document_id"] = int(document["id"])

        analysis = conn.execute(
            "INSERT INTO analyses(client_id,practice_id,analysis_type,engine,engine_version,score,rating,traffic_light,json_result,source_ids) "
            "VALUES(%s,%s,'PHANTOM/RATING','FASE7D','1.0.0-rc3-7c',88,'A','VERDE',%s::jsonb,'[]'::jsonb) RETURNING id",
            (ids["client_id"], ids["practice_id"], json.dumps({"score": 88, "rating": "A", "traffic_light": "VERDE"})),
        ).fetchone()
        ids["analysis_id"] = int(analysis["id"])

        audit = conn.execute(
            "INSERT INTO audit_events(actor,event_type,entity_type,entity_id,after_json,metadata_json) "
            "VALUES('streamlit','FASE7D_E2E','client',%s,%s::jsonb,%s::jsonb) RETURNING id",
            (str(ids["client_id"]), json.dumps(ids), json.dumps({"rollback": True, "marker": marker})),
        ).fetchone()
        ids["audit_id"] = int(audit["id"])

        joined = conn.execute(
            "SELECT c.id AS client_id,p.id AS practice_id,d.id AS document_id,a.id AS analysis_id,e.id AS audit_id "
            "FROM clients c "
            "JOIN practices p ON p.client_id=c.id "
            "JOIN documents d ON d.practice_id=p.id "
            "JOIN analyses a ON a.practice_id=p.id "
            "JOIN audit_events e ON e.entity_id=c.id::text AND e.event_type='FASE7D_E2E' "
            "WHERE c.piva=%s",
            (marker,),
        ).fetchone()
        if not joined:
            raise RuntimeError("JOIN E2E non restituisce risultati")
        conn.rollback()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    with connect() as verify:
        residual = verify.execute("SELECT COUNT(*) AS n FROM clients WHERE piva=%s", (marker,)).fetchone()["n"]
    if int(residual) != 0:
        raise RuntimeError(f"Rollback incompleto: residual={residual}")

    return {
        "ok": True,
        "version": APP_VERSION,
        "marker": marker,
        "ids_created_then_rolled_back": ids,
        "residual": int(residual),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


st.set_page_config(page_title="PLUGIN TOP_00 FASE 7D", page_icon="FP", layout="wide")
st.title("FinancePlus.Tech — PLUGIN TOP_00 FASE 7D")
st.caption(f"Streamlit runtime validation harness | MASTER {APP_VERSION}")

try:
    schema_ok, tables = schema_check()
    if not schema_ok:
        missing = sorted(REQUIRED_TABLES - set(tables))
        raise RuntimeError(f"Schema incompleto. Tabelle mancanti: {missing}")
    st.success("Neon production raggiungibile e schema MASTER verificato.")
    st.write({"database_backend": "PostgreSQL/Neon", "tables": tables})
    log("PLUGIN_TOP00_7D_SCHEMA_PASS")

    run_e2e = os.getenv("PLUGIN_TOP00_RUN_E2E_ON_START", "0") == "1"
    if run_e2e:
        result = transactional_e2e()
        st.success("E2E Streamlit → Neon superato con rollback completo.")
        st.json(result)
        log("PLUGIN_TOP00_7D_E2E_PASS residual=0")
    else:
        st.info("E2E automatico non abilitato. Schema check completato.")
except Exception as exc:
    st.error(f"FASE 7D FAIL: {type(exc).__name__}: {exc}")
    log(f"PLUGIN_TOP00_7D_FAIL {type(exc).__name__}: {exc}")
    sys.exit(1)
