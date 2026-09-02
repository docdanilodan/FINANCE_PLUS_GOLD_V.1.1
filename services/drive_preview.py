from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse


TRUSTED_DRIVE_HOSTS = {"drive.google.com"}
PREVIEWABLE_EXTENSIONS = {
    ".pdf",
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


@dataclass(frozen=True)
class ProtectedPreview:
    allowed: bool
    url: str = ""
    reason: str = ""
    ai_policy: str = "Bloccata"


def _text(fields: Mapping[str, Any], key: str) -> str:
    return str(fields.get(key) or "").strip()


def is_cse_document(fields: Mapping[str, Any]) -> bool:
    return _text(fields, "Protezione Drive").casefold() == "cse"


def _previewable_name(fields: Mapping[str, Any]) -> str:
    for key in ("Nome Definitivo", "Nome Originale", "Documento"):
        name = _text(fields, key)
        if name.casefold().endswith(tuple(PREVIEWABLE_EXTENSIONS)):
            return name
    return ""


def protected_drive_preview(fields: Mapping[str, Any]) -> ProtectedPreview:
    """Return a direct Drive preview link only for records explicitly marked CSE.

    FinancePlus never downloads or proxies the protected file. The browser is
    sent to Google Drive, where Workspace authorization and CSE key access are
    enforced. Cloud AI remains blocked independently of preview availability.
    """
    if not is_cse_document(fields):
        return ProtectedPreview(False, reason="Il documento non è classificato CSE.")

    if not _previewable_name(fields):
        return ProtectedPreview(False, reason="La preview CSE è disponibile soltanto per PDF e immagini.")

    raw_url = _text(fields, "URL Drive")
    parsed = urlparse(raw_url)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in TRUSTED_DRIVE_HOSTS:
        return ProtectedPreview(False, reason="URL Drive assente o non riconosciuto.")

    return ProtectedPreview(True, url=raw_url)
