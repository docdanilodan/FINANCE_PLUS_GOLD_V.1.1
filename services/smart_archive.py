from __future__ import annotations

import io
import mimetypes
import os
from dataclasses import asdict, dataclass, field
from typing import Any

from googleapiclient.http import MediaIoBaseUpload

from document_ai import DocumentResult, classify_text, suggested_name
from services.airtable_adapter import AirtableGold
from services.client_practice_matcher import MatchResult, match_client_practice
from services.gmail_drive_pipeline_legacy import (
    ARCHIVE_FOLDER_MAP,
    _airtable_type,
    _document_ai_policy,
    _document_sensitivity,
    _find_or_create_folder,
    _safe_folder_name,
)
from services.pdf_extraction import ExtractionResult, extract_document_content

_USE_PREVIEW = object()


@dataclass
class SmartArchivePreview:
    original_name: str
    mime_type: str
    sha256: str
    source: str = "Upload PC/cellulare"
    category: str = "Altro"
    document_type: str = "Altro"
    confidence: float = 0.0
    company_name: str = ""
    document_year: int | None = None
    reference_date: str | None = None
    proposed_name: str = ""
    extraction_method: str = "none"
    extracted_chars: int = 0
    sensitivity: str = "Interno"
    ai_policy: str = "Consentita"
    client_id: str | None = None
    client_name: str | None = None
    practice_id: str | None = None
    practice_code: str | None = None
    match_confidence: float = 0.0
    match_reason: str = "Nessuna corrispondenza certa"
    duplicate_record_id: str | None = None
    duplicate_url: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def can_archive(self) -> bool:
        return not self.duplicate_record_id

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["warnings"] = " | ".join(self.warnings)
        row["duplicate"] = "Sì" if self.duplicate_record_id else "No"
        return row


def _extension(filename: str, mime_type: str = "") -> str:
    ext = os.path.splitext(filename or "")[1]
    if ext:
        return ext.lower()
    guessed = mimetypes.guess_extension(mime_type or "") or ".bin"
    return guessed.lower()


def _classification_context(filename: str, extraction: ExtractionResult) -> str:
    return f"{filename}\n{extraction.text}"[:450_000]


def _enhanced_extraction(
    raw: bytes,
    filename: str,
    mime_type: str,
    local: ExtractionResult,
    classification: DocumentResult,
    sensitivity: str,
    ai_policy: str,
) -> tuple[ExtractionResult, DocumentResult]:
    # A cloud quality layer is considered only after local OCR/text extraction
    # established a meaningful category. This prevents an unclassified inbound
    # document from being uploaded to an external processor.
    cloud_enabled = os.getenv(
        "FINANCEPLUS_SMART_ARCHIVE_CLOUD_EXTRACTOR", "false"
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    preflight_ok = (
        cloud_enabled
        and len(local.text.strip()) >= 80
        and classification.category != "Altro"
        and classification.confidence >= 0.67
    )
    if not preflight_ok:
        return local, classification

    enhanced = extract_document_content(
        raw=raw,
        filename=filename,
        mime_type=mime_type,
        sensitivity=sensitivity,
        ai_policy=ai_policy,
        allow_cloud=True,
    )
    if not enhanced.cloud_used or len(enhanced.text) <= len(local.text):
        return local, classification
    return enhanced, classify_text(_classification_context(filename, enhanced))


def analyze_smart_document(
    raw: bytes,
    filename: str,
    mime_type: str = "",
    airtable: AirtableGold | None = None,
    source: str = "Upload PC/cellulare",
    clients: list[dict] | None = None,
    practices: list[dict] | None = None,
) -> SmartArchivePreview:
    """Locally inspect an inbound document before any durable write.

    The function performs SHA-256 deduplication, privacy-first extraction,
    FinancePlus classification and optional Cliente/Pratica matching. It never
    uploads or mutates external data.
    """
    from document_ai import sha256_bytes

    digest = sha256_bytes(raw)
    duplicate = airtable.find_one("documenti", "SHA-256", digest) if airtable else None

    local = extract_document_content(
        raw=raw,
        filename=filename,
        mime_type=mime_type,
        allow_cloud=False,
    )
    classification = classify_text(_classification_context(filename, local))
    document_type = _airtable_type(classification.category)
    sensitivity = _document_sensitivity(document_type)
    ai_policy = _document_ai_policy(sensitivity, "Standard")
    extraction, classification = _enhanced_extraction(
        raw,
        filename,
        mime_type,
        local,
        classification,
        sensitivity,
        ai_policy,
    )
    document_type = _airtable_type(classification.category)
    sensitivity = _document_sensitivity(document_type)
    ai_policy = _document_ai_policy(sensitivity, "Standard")

    match = MatchResult()
    if airtable:
        match = match_client_practice(
            airtable,
            _classification_context(filename, extraction),
            clients=clients,
            practices=practices,
        )
    if match.client_name:
        classification.company_name = match.client_name

    warnings = list(dict.fromkeys(extraction.warnings))
    if not extraction.text.strip():
        warnings.append(
            "Testo non riconosciuto: verificare categoria e cliente prima dell'archiviazione"
        )
    if classification.category == "Altro":
        warnings.append("Categoria non riconosciuta automaticamente")
    if not match.client_id:
        warnings.append("Cliente da selezionare o verificare")
    if duplicate:
        warnings.append("Duplicato SHA-256: archiviazione bloccata")

    ext = _extension(filename, mime_type)
    duplicate_fields = duplicate.get("fields", {}) if duplicate else {}
    return SmartArchivePreview(
        original_name=filename,
        mime_type=mime_type
        or mimetypes.guess_type(filename)[0]
        or "application/octet-stream",
        sha256=digest,
        source=source,
        category=classification.category,
        document_type=document_type,
        confidence=classification.confidence,
        company_name=classification.company_name,
        document_year=classification.document_year,
        reference_date=classification.reference_date,
        proposed_name=suggested_name(classification, extension=ext),
        extraction_method=extraction.method,
        extracted_chars=len(extraction.text),
        sensitivity=sensitivity,
        ai_policy=ai_policy,
        client_id=match.client_id,
        client_name=match.client_name,
        practice_id=match.practice_id,
        practice_code=match.practice_code,
        match_confidence=match.confidence,
        match_reason=match.reason,
        duplicate_record_id=duplicate.get("id") if duplicate else None,
        duplicate_url=str(duplicate_fields.get("URL Drive", "") or ""),
        warnings=warnings,
    )


def _smart_archive_destination(
    drive,
    root_folder_id: str | None,
    client_name: str | None,
    category: str,
    document_year: int | None = None,
    practice_code: str | None = None,
) -> tuple[str, str]:
    archive_root = _find_or_create_folder(
        drive, "FINANCE_V.1.1_ARCHIVIO", root_folder_id
    )
    category_name = ARCHIVE_FOLDER_MAP.get(category, "ALTRI_DOCUMENTI")

    if client_name:
        clients_root = _find_or_create_folder(drive, "CLIENTI", archive_root)
        client_folder = _safe_folder_name(client_name)
        parent = _find_or_create_folder(drive, client_folder, clients_root)
        parts = ["CLIENTI", client_folder]
        if document_year:
            year = str(int(document_year))
            parent = _find_or_create_folder(drive, year, parent)
            parts.append(year)
        if practice_code:
            practice = _safe_folder_name(practice_code, "PRATICA_DA_VERIFICARE")
            parent = _find_or_create_folder(drive, practice, parent)
            parts.append(practice)
        destination = _find_or_create_folder(drive, category_name, parent)
        parts.append(category_name)
        return destination, "/".join(parts)

    review_root = _find_or_create_folder(drive, "DA_VERIFICARE", archive_root)
    parts = ["DA_VERIFICARE"]
    if document_year:
        year = str(int(document_year))
        review_root = _find_or_create_folder(drive, year, review_root)
        parts.append(year)
    destination = _find_or_create_folder(drive, category_name, review_root)
    parts.append(category_name)
    return destination, "/".join(parts)


def archive_smart_document(
    preview: SmartArchivePreview,
    raw: bytes,
    airtable: AirtableGold,
    drive,
    drive_folder_id: str | None = None,
    *,
    client_id: str | None | object = _USE_PREVIEW,
    client_name: str | None | object = _USE_PREVIEW,
    practice_id: str | None | object = _USE_PREVIEW,
    practice_code: str | None | object = _USE_PREVIEW,
    category: str | None = None,
    document_year: int | None | object = _USE_PREVIEW,
    final_name: str | None = None,
) -> dict[str, Any]:
    """Commit a reviewed preview to Drive and Airtable as one logical action."""
    existing = airtable.find_one("documenti", "SHA-256", preview.sha256)
    if existing:
        return {
            "status": "duplicate",
            "record_id": existing.get("id"),
            "url": existing.get("fields", {}).get("URL Drive", ""),
            "name": existing.get("fields", {}).get(
                "Nome Definitivo", preview.original_name
            ),
        }

    chosen_category = category or preview.category
    chosen_type = _airtable_type(chosen_category)
    chosen_client_id = preview.client_id if client_id is _USE_PREVIEW else client_id
    chosen_client_name = (
        preview.client_name if client_name is _USE_PREVIEW else client_name
    )
    chosen_practice_id = (
        preview.practice_id if practice_id is _USE_PREVIEW else practice_id
    )
    chosen_practice_code = (
        preview.practice_code if practice_code is _USE_PREVIEW else practice_code
    )
    chosen_year = (
        preview.document_year if document_year is _USE_PREVIEW else document_year
    )
    sensitivity = _document_sensitivity(chosen_type)
    ai_policy = _document_ai_policy(sensitivity, "Standard")

    result_for_name = DocumentResult(
        category=chosen_category,
        company_name=chosen_client_name or "",
        document_year=chosen_year,
        confidence=preview.confidence,
        reference_date=preview.reference_date,
    )
    ext = _extension(preview.original_name, preview.mime_type)
    chosen_name = _safe_folder_name(
        final_name or suggested_name(result_for_name, extension=ext),
        preview.original_name,
    )
    destination_id, archive_path = _smart_archive_destination(
        drive,
        drive_folder_id,
        chosen_client_name,
        chosen_category,
        chosen_year,
        chosen_practice_code,
    )

    media = MediaIoBaseUpload(
        io.BytesIO(raw), mimetype=preview.mime_type, resumable=False
    )
    meta = {
        "name": chosen_name,
        "parents": [destination_id],
        "appProperties": {
            "financeplusSensitivity": sensitivity,
            "financeplusDocumentType": chosen_type,
            "financeplusSource": "Archivio Smart",
            "financeplusDriveProtection": "Standard",
            "financeplusAiPolicy": ai_policy,
            "financeplusSha256": preview.sha256,
        },
    }
    saved = (
        drive.files()
        .create(
            body=meta,
            media_body=media,
            fields="id,webViewLink,name,parents,appProperties",
        )
        .execute()
    )

    fields: dict[str, Any] = {
        "Documento": saved["name"],
        "Tipo Documento": chosen_type,
        "Nome Originale": preview.original_name,
        "Nome IA Suggerito": preview.proposed_name,
        "Nome Definitivo": saved["name"],
        "Origine": "Archivio Smart",
        "URL Drive": saved.get("webViewLink", ""),
        "SHA-256": preview.sha256,
        "Stato Verifica": "Da verificare",
        "Percorso nel pacchetto": archive_path,
        "Sensibilità dati": sensitivity,
        "Protezione Drive": "Standard",
        "Policy elaborazione AI": ai_policy,
    }
    if chosen_year:
        fields["Esercizio"] = int(chosen_year)
    if preview.reference_date:
        fields["Data Documento"] = preview.reference_date[:10]
    if chosen_client_id and chosen_client_name:
        fields["Cliente"] = chosen_client_name
        fields["Cliente collegato"] = [chosen_client_id]
    if chosen_practice_id:
        fields["Pratica collegata"] = [chosen_practice_id]
        fields["Pratica ID"] = chosen_practice_code or ""

    try:
        record = airtable.create_record("documenti", fields)
    except Exception:
        # Roll back only the file created by this call so a failed Airtable
        # write cannot leave an unindexed document in the archive.
        drive.files().delete(fileId=saved["id"]).execute()
        raise

    return {
        "status": "archived",
        "record_id": record.get("id"),
        "drive_file_id": saved.get("id"),
        "url": saved.get("webViewLink", ""),
        "name": saved.get("name", chosen_name),
        "path": archive_path,
    }
