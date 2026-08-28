from __future__ import annotations

import base64
import hashlib
import io
import os
import re

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from services.google_auth import load_credentials
from services.airtable_adapter import AirtableGold
from services.client_practice_matcher import match_client_practice
from document_ai import classify_text, suggested_name


AIRTABLE_TYPE_MAP = {
    "Bilancio d'esercizio": "Bilancio",
    "Ricevuta deposito Bilancio d'esercizio": "Bilancio",
    "Bozza bilancio": "Bilancio",
    "Bilancio analitico": "Situazione contabile",
    "Prospetto bilancio": "Situazione contabile",
    "Presentazione aziendale": "Altro",
    "Centrale Rischi Banca d'Italia": "Centrale Rischi",
    "Estratto conto": "Estratto conto",
    "Visura Camerale": "Visura camerale",
    "Contratto di finanziamento": "Contratto",
    "Fattura": "Fattura",
    "DURC": "DURC",
    "Preventivo": "Preventivo",
    "Offerta": "Altro",
    "Curriculum Vitae": "Altro",
    "Altro": "Altro",
}

ARCHIVE_FOLDER_MAP = {
    "Bilancio d'esercizio": "BILANCI_ESERCIZIO",
    "Ricevuta deposito Bilancio d'esercizio": "RICEVUTE_DEPOSITO_BILANCI",
    "Bozza bilancio": "BOZZE_BILANCIO",
    "Bilancio analitico": "BILANCI_ANALITICI",
    "Prospetto bilancio": "PROSPETTI_BILANCIO",
    "Presentazione aziendale": "PRESENTAZIONI_AZIENDALI",
    "Centrale Rischi Banca d'Italia": "CENTRALE_RISCHI",
    "Estratto conto": "ESTRATTI_CONTO",
    "Visura Camerale": "VISURE_CAMERALI",
    "Contratto di finanziamento": "CONTRATTI_FINANZIAMENTO",
    "Fattura": "FATTURE",
    "DURC": "DURC",
    "Preventivo": "PREVENTIVI",
    "Offerta": "OFFERTE",
    "Curriculum Vitae": "CURRICULUM",
    "Altro": "ALTRI_DOCUMENTI",
}


def _walk(parts):
    for part in parts or []:
        yield part
        yield from _walk(part.get("parts", []))


def _already_indexed(airtable: AirtableGold, table: str, field: str, value: str) -> bool:
    return bool(value and airtable.find_one(table, field, value))


def _safe_folder_name(value: str, fallback: str = "CLIENTE_DA_VERIFICARE") -> str:
    clean = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", str(value or ""))
    clean = re.sub(r"\s+", " ", clean).strip(" ._")
    return clean or fallback


def _escape_drive_query(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace("'", "\\'")


def _find_or_create_folder(drive, name: str, parent_id: str | None = None) -> str:
    name = _safe_folder_name(name)
    clauses = [
        f"name = '{_escape_drive_query(name)}'",
        "mimeType = 'application/vnd.google-apps.folder'",
        "trashed = false",
    ]
    if parent_id:
        clauses.append(f"'{_escape_drive_query(parent_id)}' in parents")
    found = drive.files().list(
        q=" and ".join(clauses),
        spaces="drive",
        fields="files(id,name,parents)",
        pageSize=10,
    ).execute().get("files", [])
    if found:
        return found[0]["id"]

    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    return drive.files().create(body=body, fields="id").execute()["id"]


def _archive_destination(drive, root_folder_id: str | None, client_name: str | None, category: str) -> tuple[str | None, str]:
    """Return the folder id and a human-readable archive path."""
    root = root_folder_id
    archive_root = _find_or_create_folder(drive, "FINANCE_V.1.1_ARCHIVIO", root)
    clients_root = _find_or_create_folder(drive, "CLIENTI", archive_root)

    if client_name:
        client_folder_name = _safe_folder_name(client_name)
        client_root = _find_or_create_folder(drive, client_folder_name, clients_root)
        docs_root = _find_or_create_folder(drive, "DOCUMENTI", client_root)
        category_name = ARCHIVE_FOLDER_MAP.get(category, "ALTRI_DOCUMENTI")
        destination = _find_or_create_folder(drive, category_name, docs_root)
        return destination, f"CLIENTI/{client_folder_name}/DOCUMENTI/{category_name}"

    review_root = _find_or_create_folder(drive, "DA_VERIFICARE", archive_root)
    category_name = ARCHIVE_FOLDER_MAP.get(category, "ALTRI_DOCUMENTI")
    destination = _find_or_create_folder(drive, category_name, review_root)
    return destination, f"DA_VERIFICARE/{category_name}"


def _airtable_type(category: str) -> str:
    return AIRTABLE_TYPE_MAP.get(category, "Altro")


def sync_gmail_attachments(
    query: str = "has:attachment newer_than:1d -in:spam -in:trash",
    drive_folder_id: str | None = None,
    max_messages: int = 50,
) -> dict:
    """Archive new Gmail attachments to Drive and index them in Airtable.

    Behaviour:
    - exact duplicates are blocked by SHA-256 before upload;
    - confident client matches are stored under that client's archive;
    - uncertain matches are never assigned to a client and go to DA_VERIFICARE;
    - semantic verification remains separate: new records stay Da verificare.
    """
    creds = load_credentials()
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    airtable = AirtableGold()
    result = {
        "messages": 0,
        "attachments": 0,
        "uploaded": 0,
        "duplicates": 0,
        "matched": 0,
        "archived_by_client": 0,
        "pending_review": 0,
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

            if _already_indexed(airtable, "email", "Gmail Message ID", msg["id"]):
                result["duplicates"] += 1
                continue

            context = " ".join(
                [headers.get("subject", ""), headers.get("from", ""), msg.get("snippet", "")]
            )
            match = match_client_practice(airtable, context)
            confident_client = bool(match.client_id and match.confidence >= 0.80)
            if confident_client:
                result["matched"] += 1

            for part in _walk(msg["payload"].get("parts", [])):
                filename = part.get("filename", "")
                attachment_id = part.get("body", {}).get("attachmentId")
                if not filename or not attachment_id:
                    continue

                result["attachments"] += 1
                encoded = gmail.users().messages().attachments().get(
                    userId="me",
                    messageId=msg["id"],
                    id=attachment_id,
                ).execute()["data"]
                raw = base64.urlsafe_b64decode(encoded + "===")
                sha = hashlib.sha256(raw).hexdigest()

                if _already_indexed(airtable, "documenti", "SHA-256", sha):
                    result["duplicates"] += 1
                    continue

                classification = classify_text(filename + " " + context)
                ext = os.path.splitext(filename)[1] or ".bin"
                if confident_client:
                    classification.company_name = match.client_name or ""
                proposed = suggested_name(classification, extension=ext)

                destination_id, archive_path = _archive_destination(
                    drive,
                    drive_folder_id,
                    match.client_name if confident_client else None,
                    classification.category,
                )

                media = MediaIoBaseUpload(
                    io.BytesIO(raw),
                    mimetype=part.get("mimeType") or "application/octet-stream",
                    resumable=False,
                )
                meta = {"name": proposed or filename, "parents": [destination_id]}
                saved = drive.files().create(
                    body=meta,
                    media_body=media,
                    fields="id,webViewLink,name,parents",
                ).execute()
                result["uploaded"] += 1

                fields = {
                    "Documento": saved["name"],
                    "Tipo Documento": _airtable_type(classification.category),
                    "Nome Originale": filename,
                    "Nome IA Suggerito": saved["name"],
                    "Nome Definitivo": saved["name"],
                    "Origine": "Gmail",
                    "URL Drive": saved.get("webViewLink", ""),
                    "SHA-256": sha,
                    "Stato Verifica": "Da verificare",
                    "Percorso nel pacchetto": archive_path,
                }

                if confident_client:
                    fields["Cliente"] = match.client_name or ""
                    fields["Cliente collegato"] = [match.client_id]
                    result["archived_by_client"] += 1
                else:
                    result["pending_review"] += 1

                if match.practice_id and confident_client:
                    fields["Pratica ID"] = match.practice_code or ""
                    fields["Pratica collegata"] = [match.practice_id]

                airtable.create_record("documenti", fields)

            email_fields = {
                "Oggetto": headers.get("subject", "(senza oggetto)"),
                "Mittente": headers.get("from", ""),
                "Gmail Message ID": msg["id"],
                "Sintesi IA": msg.get("snippet", ""),
            }
            if confident_client:
                email_fields["Cliente"] = match.client_name or ""
                email_fields["Cliente collegato"] = [match.client_id]
            if match.practice_id and confident_client:
                email_fields["Pratica ID"] = match.practice_code or ""
                email_fields["Pratica collegata"] = [match.practice_id]
            airtable.create_record("email", email_fields)

        except Exception as exc:
            result["errors"].append({"message_id": item.get("id"), "error": str(exc)})

    return result
