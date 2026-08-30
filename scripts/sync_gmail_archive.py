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


def main() -> int:
    if not os.getenv("AIRTABLE_TOKEN", "").strip():
        print("ARCHIVE_SKIPPED missing environment secret: AIRTABLE_TOKEN")
        return 0

    profiles = discover_google_profiles()
    if not profiles:
        print("ARCHIVE_SKIPPED no Google OAuth profiles configured")
        return 0

    query = os.getenv(
        "FINANCEPLUS_GMAIL_QUERY",
        "has:attachment newer_than:2d -in:spam -in:trash",
    )
    try:
        max_messages = int(os.getenv("FINANCEPLUS_MAX_MESSAGES", "100"))
    except ValueError:
        max_messages = 100

    results: dict[str, dict] = {}
    for profile in profiles:
        env_name = token_env_name(profile)
        if not os.getenv(env_name, "").strip():
            results[profile] = {"status": "skipped", "reason": f"{env_name} non configurato"}
            continue
        try:
            results[profile] = sync_gmail_attachments(
                query=query,
                drive_folder_id=_drive_folder_for_profile(profile),
                max_messages=max_messages,
                profile=profile,
            )
        except Exception as exc:
            results[profile] = {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    print(json.dumps({"profiles": profiles, "results": results}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
