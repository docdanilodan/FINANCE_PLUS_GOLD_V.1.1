from __future__ import annotations

import json
import os
import sys

from services.gmail_drive_pipeline import sync_gmail_attachments
from services.google_auth import discover_google_profiles, token_env_name


def _drive_folder_for_profile(profile: str) -> str | None:
    if profile == "DEFAULT":
        return os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip() or None
    return os.getenv(f"GOOGLE_DRIVE_FOLDER_ID_{profile}", "").strip() or os.getenv(
        "GOOGLE_DRIVE_FOLDER_ID", ""
    ).strip() or None


def _required(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def main() -> int:
    missing = [name for name in ("AIRTABLE_TOKEN", "AIRTABLE_BASE_ID") if not _required(name)]
    if missing:
        print(f"ARCHIVE_BLOCKED missing environment secret(s): {', '.join(missing)}")
        return 2

    profiles = discover_google_profiles()
    if not profiles:
        print("ARCHIVE_BLOCKED no Google OAuth profiles configured")
        return 2

    query = os.getenv(
        "FINANCEPLUS_GMAIL_QUERY",
        "has:attachment newer_than:2d -in:spam -in:trash",
    )
    try:
        max_messages = int(os.getenv("FINANCEPLUS_MAX_MESSAGES", "100"))
    except ValueError:
        max_messages = 100

    results: dict[str, dict] = {}
    attempted = 0
    failures = 0
    for profile in profiles:
        env_name = token_env_name(profile)
        if not _required(env_name):
            results[profile] = {"status": "blocked", "reason": f"{env_name} non configurato"}
            failures += 1
            continue

        drive_folder = _drive_folder_for_profile(profile)
        if not drive_folder:
            results[profile] = {"status": "blocked", "reason": "Google Drive folder non configurata"}
            failures += 1
            continue

        attempted += 1
        try:
            results[profile] = sync_gmail_attachments(
                query=query,
                drive_folder_id=drive_folder,
                max_messages=max_messages,
                profile=profile,
            )
        except Exception as exc:
            failures += 1
            results[profile] = {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    print(json.dumps({"profiles": profiles, "results": results}, ensure_ascii=False, indent=2, default=str))

    if attempted == 0:
        print("ARCHIVE_BLOCKED no fully configured Google profile")
        return 2
    if failures:
        print(f"ARCHIVE_PARTIAL_FAILURE failures={failures}")
        return 1

    print(f"ARCHIVE_OK profiles={attempted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())