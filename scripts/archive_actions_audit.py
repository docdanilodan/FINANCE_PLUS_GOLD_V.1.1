from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

from services.actions_audit import AUDIT_BRANCH, actions_audit_path, build_actions_audit_record


WRITE_RETRIES = 5


def _response_json(response: requests.Response) -> dict:
    response.raise_for_status()
    return response.json()


def _ensure_audit_branch(session: requests.Session, api_url: str, repository: str, default_branch: str) -> None:
    encoded_audit_ref = quote(f"heads/{AUDIT_BRANCH}", safe="")
    response = session.get(f"{api_url}/repos/{repository}/git/ref/{encoded_audit_ref}", timeout=30)
    if response.status_code == 200:
        return
    if response.status_code != 404:
        response.raise_for_status()

    encoded_default_ref = quote(f"heads/{default_branch}", safe="")
    source = _response_json(
        session.get(f"{api_url}/repos/{repository}/git/ref/{encoded_default_ref}", timeout=30)
    )
    created = session.post(
        f"{api_url}/repos/{repository}/git/refs",
        json={"ref": f"refs/heads/{AUDIT_BRANCH}", "sha": source["object"]["sha"]},
        timeout=30,
    )
    if created.status_code in {409, 422}:
        # Another audit run may have created the branch after our first GET.
        concurrent = session.get(f"{api_url}/repos/{repository}/git/ref/{encoded_audit_ref}", timeout=30)
        if concurrent.status_code == 200:
            return
    _response_json(created)


def _write_audit_record(
    session: requests.Session,
    api_url: str,
    repository: str,
    path: str,
    record: dict,
) -> None:
    encoded_path = quote(path, safe="/")
    url = f"{api_url}/repos/{repository}/contents/{encoded_path}"
    for attempt in range(WRITE_RETRIES):
        existing = session.get(url, params={"ref": AUDIT_BRANCH}, timeout=30)
        payload = {
            "message": f"Archive Actions run {record['run_id']} attempt {record['run_attempt']}",
            "content": base64.b64encode(
                (json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
            ).decode("ascii"),
            "branch": AUDIT_BRANCH,
        }
        if existing.status_code == 200:
            payload["sha"] = existing.json()["sha"]
        elif existing.status_code != 404:
            existing.raise_for_status()

        written = session.put(url, json=payload, timeout=30)
        if written.status_code not in {409, 422}:
            _response_json(written)
            return
        if attempt == WRITE_RETRIES - 1:
            written.raise_for_status()
        # The audit branch advanced concurrently. Refresh the file SHA and retry.
        time.sleep(min(2**attempt, 8))


def _jobs_url_for_attempt(api_url: str, repository: str, run: dict) -> str:
    run_id = int(run["id"])
    run_attempt = int(run.get("run_attempt") or 1)
    return f"{api_url}/repos/{repository}/actions/runs/{run_id}/attempts/{run_attempt}/jobs"


def main() -> int:
    event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    default_branch = os.environ.get("GITHUB_DEFAULT_BRANCH", "main").strip() or "main"
    if not event_path.is_file() or not token or not repository:
        print("ACTIONS_AUDIT_ERROR evento, repository o token GitHub non configurato")
        return 1

    event = json.loads(event_path.read_text(encoding="utf-8"))
    run = event.get("workflow_run") or {}
    if run.get("status") != "completed":
        print("ACTIONS_AUDIT_SKIPPED workflow non completato")
        return 0

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    jobs_url = _jobs_url_for_attempt(api_url, repository, run)
    jobs = _response_json(session.get(jobs_url, params={"per_page": 100}, timeout=30))
    record = build_actions_audit_record(run, jobs.get("jobs", []))
    path = actions_audit_path(record)
    _ensure_audit_branch(session, api_url, repository, default_branch)
    _write_audit_record(session, api_url, repository, path, record)
    print(f"ACTIONS_AUDIT_ARCHIVED branch={AUDIT_BRANCH} path={path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
