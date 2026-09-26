from __future__ import annotations
class GmailAdapter:
    def sync(self, **kwargs):
        from services.gmail_drive_pipeline_v2 import sync_gmail_attachments
        return sync_gmail_attachments(**kwargs)
class ArubaAdapter:
    def sync(self, **kwargs):
        from services.aruba_imap_pipeline import sync_aruba_account
        return sync_aruba_account(**kwargs)
