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
