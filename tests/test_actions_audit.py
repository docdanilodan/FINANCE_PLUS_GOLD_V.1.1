import scripts.archive_actions_audit as audit_script
from services.actions_audit import actions_audit_path, build_actions_audit_record


def test_actions_audit_keeps_metadata_and_excludes_raw_logs():
    run = {
        "id": 123,
        "run_number": 7,
        "run_attempt": 2,
        "name": "FinancePlus unified CI",
        "workflow_id": 44,
        "event": "pull_request",
        "status": "completed",
        "conclusion": "failure",
        "head_branch": "feature/test",
        "head_sha": "abc123",
        "actor": {"login": "tester"},
        "repository": {"full_name": "owner/repo"},
        "created_at": "2026-09-02T10:00:00Z",
        "updated_at": "2026-09-02T10:01:00Z",
        "html_url": "https://github.com/owner/repo/actions/runs/123",
        "logs": "must not be copied",
    }
    jobs = [
        {
            "id": 9,
            "name": "test",
            "status": "completed",
            "conclusion": "failure",
            "steps": [{"number": 1, "name": "Run tests", "conclusion": "failure", "log": "secret"}],
        }
    ]
    record = build_actions_audit_record(run, jobs)
    assert record["run_id"] == 123
    assert record["jobs"][0]["steps"][0]["name"] == "Run tests"
    assert "logs" not in record
    assert "log" not in record["jobs"][0]["steps"][0]
    assert actions_audit_path(record) == "actions-audit/2026/09/123-attempt-2.json"


def test_jobs_url_targets_the_workflow_run_attempt():
    url = audit_script._jobs_url_for_attempt(
        "https://api.github.com",
        "owner/repo",
        {"id": 123, "run_attempt": 2},
    )
    assert url.endswith("/actions/runs/123/attempts/2/jobs")


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _ConflictingWriteSession:
    def __init__(self):
        self.put_calls = 0

    def get(self, *args, **kwargs):
        return _Response(404)

    def put(self, *args, **kwargs):
        self.put_calls += 1
        return _Response(409 if self.put_calls == 1 else 201, {"content": {}})


def test_audit_write_retries_after_concurrent_branch_advance(monkeypatch):
    session = _ConflictingWriteSession()
    monkeypatch.setattr(audit_script.time, "sleep", lambda seconds: None)
    audit_script._write_audit_record(
        session,
        "https://api.github.com",
        "owner/repo",
        "actions-audit/2026/09/123-attempt-1.json",
        {"run_id": 123, "run_attempt": 1},
    )
    assert session.put_calls == 2
