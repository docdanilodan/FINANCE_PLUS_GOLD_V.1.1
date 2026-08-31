from __future__ import annotations

"""Compatibility facade for the FinancePlus Gmail/Drive archive.

Existing imports keep working while the default sync implementation is routed
to the v2 content-aware pipeline. Legacy constants and helper functions remain
available to avoid breaking callers during the migration.
"""

from services import gmail_drive_pipeline_legacy as _legacy

for _name in dir(_legacy):
    if _name.startswith("__") or _name == "sync_gmail_attachments":
        continue
    globals()[_name] = getattr(_legacy, _name)

from services.gmail_drive_pipeline_v2 import sync_gmail_attachments

__all__ = ["sync_gmail_attachments"]
