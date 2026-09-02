from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


AUDIT_BRANCH = "audit/actions-history"


def _text(value: Any, limit: int = 300) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def build_actions_audit_record(run: Mapping[str, Any], jobs: Iterable[Mapping[str, Any]]) -> dict:
    """Create a metadata-only record; raw logs, artifacts and secrets are excluded."""
    safe_jobs = []
    for job in jobs:
        safe_steps = [
            {
                "number": step.get("number"),
                "name": _text(step.get("name")),
                "status": _text(step.get("status"), 40),
                "conclusion": _text(step.get("conclusion"), 40),
            }
            for step in (job.get("steps") or [])
        ]
        safe_jobs.append(
            {
                "id": job.get("id"),
                "name": _text(job.get("name")),
                "status": _text(job.get("status"), 40),
                "conclusion": _text(job.get("conclusion"), 40),
                "started_at": _text(job.get("started_at"), 50),
                "completed_at": _text(job.get("completed_at"), 50),
                "steps": safe_steps,
            }
        )

    actor = run.get("actor") or {}
    repository = run.get("repository") or {}
    return {
        "schema_version": 1,
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "repository": _text(repository.get("full_name"), 200),
        "workflow_name": _text(run.get("name"), 200),
        "workflow_id": run.get("workflow_id"),
        "run_id": run.get("id"),
        "run_number": run.get("run_number"),
        "run_attempt": int(run.get("run_attempt") or 1),
        "event": _text(run.get("event"), 80),
        "status": _text(run.get("status"), 40),
        "conclusion": _text(run.get("conclusion"), 40),
        "head_branch": _text(run.get("head_branch"), 200),
        "head_sha": _text(run.get("head_sha"), 80),
        "actor": _text(actor.get("login"), 100),
        "created_at": _text(run.get("created_at"), 50),
        "updated_at": _text(run.get("updated_at"), 50),
        "html_url": _text(run.get("html_url"), 500),
        "jobs": safe_jobs,
    }


def actions_audit_path(record: Mapping[str, Any]) -> str:
    created = _text(record.get("created_at"), 50)
    match = re.match(r"(\d{4})-(\d{2})", created)
    year, month = match.groups() if match else ("unknown", "unknown")
    run_id = int(record.get("run_id") or 0)
    attempt = int(record.get("run_attempt") or 1)
    return f"actions-audit/{year}/{month}/{run_id}-attempt-{attempt}.json"
