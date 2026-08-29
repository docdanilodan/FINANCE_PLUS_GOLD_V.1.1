from __future__ import annotations

import json
import os
from datetime import date, timedelta

from services.aruba_imap_pipeline import sync_aruba_attachments


DEFAULT_BACKFILL_DATE = "2026-01-01"


def _days_ago(days: int) -> str:
    return (date.today() - timedelta(days=max(0, days))).isoformat()


def _accounts() -> list[tuple[str, str]]:
    return [
        (
            os.getenv("ARUBA_D_DANGELO_EMAIL", "d.dangelo@financeplus.tech").strip(),
            os.getenv("ARUBA_D_DANGELO_PASSWORD", "").strip(),
        ),
        (
            os.getenv("ARUBA_PRATICHE_EMAIL", "pratiche@financeplus.tech").strip(),
            os.getenv("ARUBA_PRATICHE_PASSWORD", "").strip(),
        ),
    ]


def _since_date() -> str:
    explicit = os.getenv("FINANCEPLUS_ARUBA_SINCE_DATE", "").strip()
    if explicit:
        return explicit
    since_days = os.getenv("FINANCEPLUS_ARUBA_SINCE_DAYS", "").strip()
    if since_days:
        return _days_ago(int(since_days))
    return DEFAULT_BACKFILL_DATE


def main() -> int:
    max_messages = int(os.getenv("FINANCEPLUS_ARUBA_MAX_MESSAGES", "200"))
    drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip() or None
    since = _since_date()

    summary = {
        "since": since,
        "accounts": [],
        "totals": {
            "messages": 0,
            "attachments": 0,
            "uploaded": 0,
            "duplicates": 0,
            "duplicate_sources_updated": 0,
            "matched": 0,
            "archived_by_client": 0,
            "pending_review": 0,
            "client_updates": 0,
            "skipped_indexed_messages": 0,
            "errors": 0,
        },
    }

    configured = 0
    for email_address, password in _accounts():
        if not email_address or not password:
            summary["accounts"].append(
                {
                    "account": email_address or "(non configurato)",
                    "status": "skipped",
                    "reason": "password non configurata",
                }
            )
            continue

        configured += 1
        try:
            result = sync_aruba_attachments(
                account_email=email_address,
                password=password,
                since=since,
                drive_folder_id=drive_folder_id,
                max_messages=max_messages,
            )
            result["status"] = "ok"
            summary["accounts"].append(result)
            for key in (
                "messages",
                "attachments",
                "uploaded",
                "duplicates",
                "duplicate_sources_updated",
                "matched",
                "archived_by_client",
                "pending_review",
                "client_updates",
                "skipped_indexed_messages",
            ):
                summary["totals"][key] += int(result.get(key, 0) or 0)
            summary["totals"]["errors"] += len(result.get("errors") or [])
        except Exception as exc:
            summary["accounts"].append(
                {
                    "account": email_address,
                    "status": "error",
                    "error": str(exc),
                }
            )
            summary["totals"]["errors"] += 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if configured == 0:
        print("Nessuna casella Aruba configurata: aggiungere le password nei GitHub Actions Secrets.")
        return 2

    return 1 if summary["totals"]["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
