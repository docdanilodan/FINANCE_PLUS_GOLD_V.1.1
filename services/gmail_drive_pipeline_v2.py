from __future__ import annotations

import base64
import hashlib
import io
import os

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from document_ai import classify_text, suggested_name
from services.airtable_adapter import AirtableGold
from services.client_practice_matcher import match_client_practice
from services.drive_classification import ai_policy_for_sensitivity, resolve_drive_classification
from services.google_auth import load_credentials
from services.pdf_extraction import extract_document_content
from services import gmail_drive_pipeline_legacy as legacy


def _classify_with_local_preflight(raw: bytes, filename: str, mime_type: str, context: str):
    """Classify inbound content locally before any optional cloud extraction."""
    local = extract_document_content(
        raw=raw,
        filename=filename,
        mime_type=mime_type,
        sensitivity="Altamente riservato",
        ai_policy="Bloccata",
        allow_cloud=False,
    )
    local_context = f"{filename} {context}\n{local.text}"[:450_000]
    classification = classify_text(local_context)
    document_type = legacy._airtable_type(classification.category)
    sensitivity = legacy._document_sensitivity(document_type)
    ai_policy = legacy._document_ai_policy(sensitivity, "Standard")
    return classification, document_type, sensitivity, ai_policy, local


def _maybe_enhance_with_adobe(
    raw: bytes,
    filename: str,
    mime_type: str,
    context: str,
    sensitivity: str,
    ai_policy: str,
    local_result,
):
    enhanced = extract_document_content(
        raw=raw,
        filename=filename,
        mime_type=mime_type,
        sensitivity=sensitivity,
        ai_policy=ai_policy,
        allow_cloud=True,
    )
    if not enhanced.cloud_used:
        return None, local_result
    classification = classify_text(f"{filename} {context}\n{enhanced.text}"[:450_000])
    return classification, enhanced


def sync_gmail_attachments(
    query: str = "has:attachment newer_than:1d -in:spam -in:trash",
    drive_folder_id: str | None = None,
    max_messages: int = 50,
    profile: str | None = None,
) -> dict:
    """FinancePlus Gmail archive v2.

    Differences from the legacy pipeline:
    - extracts actual PDF text before classification;
    - performs local privacy preflight before optional Adobe PDF-to-Markdown;
    - reads Google Drive labels and raises sensitivity when a configured label
      requires a stricter policy;
    - records the extraction method in Drive appProperties for auditability.
    """
    creds = load_credentials(profile)
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    airtable = AirtableGold()
    source_email = gmail.users().getProfile(userId="me").execute().get("emailAddress", "Gmail")
    result = {
        "pipeline": "v2-content-aware",
        "profile": profile or "DEFAULT",
        "source_email": source_email,
        "messages": 0,
        "attachments": 0,
        "uploaded": 0,
        "duplicates": 0,
        "duplicate_sources_updated": 0,
        "matched": 0,
        "archived_by_client": 0,
        "pending_review": 0,
        "adobe_markdown": 0,
        "drive_label_overrides": 0,
        "extraction_warnings": 0,
        "errors": [],
    }

    ids = gmail.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_messages,
    ).execute().get("messages", [])

    for item in ids:
        try:
            msg = gmail.users().messages().get(
                userId="me",
                id=item["id"],
                format="full",
            ).execute()
            result["messages"] += 1
            headers = {
                header["name"].lower(): header["value"]
                for header in msg["payload"].get("headers", [])
            }
            source_key = f"GMAIL:{source_email.casefold()}:{msg['id']}"

            if legacy._already_indexed(airtable, "email", "Message ID sorgente", source_key):
                result["duplicates"] += 1
                continue

            context = " ".join(
                [headers.get("subject", ""), headers.get("from", ""), msg.get("snippet", "")]
            )
            email_match = match_client_practice(airtable, context)
            email_confident = bool(email_match.client_id and email_match.confidence >= 0.80)
            attachment_names: list[str] = []

            for part in legacy._walk(msg["payload"].get("parts", [])):
                filename = part.get("filename", "")
                attachment_id = part.get("body", {}).get("attachmentId")
                if not filename or not attachment_id:
                    continue

                attachment_names.append(filename)
                result["attachments"] += 1
                encoded = gmail.users().messages().attachments().get(
                    userId="me",
                    messageId=msg["id"],
                    id=attachment_id,
                ).execute()["data"]
                raw = base64.urlsafe_b64decode(encoded + "===")
                sha = hashlib.sha256(raw).hexdigest()

                if legacy._register_duplicate_source(airtable, sha, source_email):
                    result["duplicates"] += 1
                    result["duplicate_sources_updated"] += 1
                    continue

                attachment_context = f"{filename} {context}"
                file_match = match_client_practice(airtable, attachment_context)
                confident_client = bool(file_match.client_id and file_match.confidence >= 0.80)
                if confident_client:
                    result["matched"] += 1

                mime_type = part.get("mimeType") or "application/octet-stream"
                classification, document_type, sensitivity, ai_policy, extraction = _classify_with_local_preflight(
                    raw=raw,
                    filename=filename,
                    mime_type=mime_type,
                    context=context,
                )
                if extraction.warnings:
                    result["extraction_warnings"] += len(extraction.warnings)

                enhanced_classification, enhanced = _maybe_enhance_with_adobe(
                    raw=raw,
                    filename=filename,
                    mime_type=mime_type,
                    context=context,
                    sensitivity=sensitivity,
                    ai_policy=ai_policy,
                    local_result=extraction,
                )
                if enhanced_classification is not None:
                    classification = enhanced_classification
                    extraction = enhanced
                    document_type = legacy._airtable_type(classification.category)
                    sensitivity = legacy._document_sensitivity(document_type)
                    ai_policy = legacy._document_ai_policy(sensitivity, "Standard")
                    result["adobe_markdown"] += 1

                protection = "Standard"
                ext = os.path.splitext(filename)[1] or ".bin"
                if confident_client:
                    classification.company_name = file_match.client_name or ""
                proposed = suggested_name(classification, extension=ext)

                destination_id, archive_path = legacy._archive_destination(
                    drive,
                    drive_folder_id,
                    file_match.client_name if confident_client else None,
                    classification.category,
                )

                media = MediaIoBaseUpload(
                    io.BytesIO(raw),
                    mimetype=mime_type,
                    resumable=False,
                )
                meta = {
                    "name": proposed or filename,
                    "parents": [destination_id],
                    "appProperties": {
                        "financeplusSensitivity": sensitivity,
                        "financeplusDocumentType": document_type,
                        "financeplusSource": "Gmail",
                        "financeplusDriveProtection": protection,
                        "financeplusAiPolicy": ai_policy,
                        "financeplusExtractionMethod": extraction.method[:120],
                    },
                }
                saved = drive.files().create(
                    body=meta,
                    media_body=media,
                    fields="id,webViewLink,name,parents,appProperties",
                ).execute()
                result["uploaded"] += 1

                drive_decision = resolve_drive_classification(
                    drive=drive,
                    file_id=saved["id"],
                    fallback=sensitivity,
                )
                if drive_decision.sensitivity != sensitivity:
                    sensitivity = drive_decision.sensitivity
                    ai_policy = ai_policy_for_sensitivity(sensitivity, protection)
                    result["drive_label_overrides"] += 1
                    props = dict(saved.get("appProperties", {}) or meta["appProperties"])
                    props.update(
                        {
                            "financeplusSensitivity": sensitivity,
                            "financeplusAiPolicy": ai_policy,
                            "financeplusClassificationSource": drive_decision.source,
                        }
                    )
                    drive.files().update(
                        fileId=saved["id"],
                        body={"appProperties": props},
                        fields="id,appProperties",
                    ).execute()

                fields = {
                    "Documento": saved["name"],
                    "Tipo Documento": document_type,
                    "Nome Originale": filename,
                    "Nome IA Suggerito": saved["name"],
                    "Nome Definitivo": saved["name"],
                    "Origine": "Gmail",
                    "Caselle origine": source_email,
                    "Casella sorgente": source_email,
                    "URL Drive": saved.get("webViewLink", ""),
                    "SHA-256": sha,
                    "Stato Verifica": "Da verificare",
                    "Percorso nel pacchetto": archive_path,
                    "Sensibilità dati": sensitivity,
                    "Protezione Drive": protection,
                    "Policy elaborazione AI": ai_policy,
                }

                if confident_client:
                    fields["Cliente"] = file_match.client_name or ""
                    fields["Cliente collegato"] = [file_match.client_id]
                    result["archived_by_client"] += 1
                else:
                    result["pending_review"] += 1

                if file_match.practice_id and confident_client:
                    fields["Pratica ID"] = file_match.practice_code or ""
                    fields["Pratica collegata"] = [file_match.practice_id]

                airtable.create_record("documenti", fields)

            email_fields = {
                "Oggetto": headers.get("subject", "(senza oggetto)"),
                "Mittente": headers.get("from", ""),
                "Gmail Message ID": msg["id"],
                "Casella origine": source_email,
                "Casella sorgente": source_email,
                "Message ID sorgente": source_key,
                "Sintesi IA": msg.get("snippet", ""),
                "Allegati": "\n".join(attachment_names),
            }
            if email_confident:
                email_fields["Cliente"] = email_match.client_name or ""
                email_fields["Cliente collegato"] = [email_match.client_id]
            if email_match.practice_id and email_confident:
                email_fields["Pratica ID"] = email_match.practice_code or ""
                email_fields["Pratica collegata"] = [email_match.practice_id]
            airtable.create_record("email", email_fields)

        except Exception as exc:
            result["errors"].append({"message_id": item.get("id"), "error": str(exc)})

    return result
