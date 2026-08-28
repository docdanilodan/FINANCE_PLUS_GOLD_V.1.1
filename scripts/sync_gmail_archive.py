from __future__ import annotations

import json
import os
import sys

from services.gmail_drive_pipeline import sync_gmail_attachments


REQUIRED_ENV = ("AIRTABLE_TOKEN", "GOOGLE_OAUTH_TOKEN_JSON")


def main() -> int:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name, "").strip()]
    if missing:
        print("ARCHIVE_SKIPPED missing environment secrets: " + ", ".join(missing))
        return 0

    root_folder = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip() or None
    query = os.getenv(
        "FINANCEPLUS_GMAIL_QUERY",
        "has:attachment newer_than:2d -in:spam -in:trash",
    )
    try:
        max_messages = int(os.getenv("FINANCEPLUS_MAX_MESSAGES", "100"))
    except ValueError:
        max_messages = 100

    result = sync_gmail_attachments(
        query=query,
        drive_folder_id=root_folder,
        max_messages=max_messages,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    # Individual attachment errors are reported but do not abort the next run.
    # Authentication/configuration exceptions still fail the job visibly.
    return 0


if __name__ == "__main__":
    sys.exit(main())
