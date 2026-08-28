from __future__ import annotations

import hashlib
import imaplib
import io
import os
import ssl
from datetime import date
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from pypdf import PdfReader

from document_ai import classify_text, suggested_name
from services.airtable_adapter import AirtableGold
from services.client_practice_matcher import match_client_practice
from services.gmail_drive_pipeline import _airtable_type, _archive_destination
from services.google_auth import load_credentials

DEFAULT_IMAP_HOST = "imaps.aruba.it"
DEFAULT_IMAP_PORT = 993


def _connect(account_email: str, password: str, host: str = DEFAULT_IMAP_HOST, port: int = DEFAULT_IMAP_PORT):
    if not account_email or not password:
        raise ValueError("Email e password Aruba sono obbligatorie.")
    context = ssl.create_default_context()
    client = imaplib.IMAP4_SSL(host=host, port=int(port), ssl_context=context)
    client.login(account_email, password)
    return client


def test_aruba_connection(
    account_email: str,
    password: str,
    host: str = DEFAULT_IMAP_HOST,
    port: int = DEFAULT_IMAP_PORT,
) -> dict:
    client = _connect(account_email, password, host, port)
    try:
        status, data = client.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError("Impossibile aprire INBOX.")
        count = int((data or [b"0"])[0] or 0)
        return {"ok": True, "account": account_email, "inbox_messages": count}
    finally:
        try:
            client.logout()
        except Exception:
            pass


def _decode_text(part) -> str:
    try:
        payload = part.get_payload(decode=True) or b""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    except Exception:
        return ""


def _message_body(msg) -> str:
    chunks: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain":
                chunks.append(_decode_text(part))
    elif msg.get_content_type() == "text/plain":
        chunks.append(_decode_text(msg))
    return "\n".join(chunks).strip()


def _attachment_text(filename: str, mime_type: str, raw: bytes) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    try:
        if ext == ".pdf" or mime_type == "application/pdf":
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join((page.extract_text() or "") for page in reader.pages)[:120000]
        if ext in {".txt", ".csv", ".md", ".xml", ".json"} or mime_type.startswith("text/"):
            return raw.decode("utf-8", errors="replace")[:120000]
    except Exception:
        return ""
    return ""


def _imap_since(value: str | date | None) -> str:
    if value is None:
        d = date.today()
    elif isinstance(value, date):
        d = value
    else:
        d = date.fromisoformat(str(value))
    return d.strftime("%d-%b-%Y")


def _message_datetime(msg) -> str | None:
    raw = str(msg.get("Date") or "").strip()
    if not raw:
        return None
    try:
        return parsedate_to_datetime(raw).isoformat()
    except Exception:
        return None


def _append_source(existing: str, account_email: str) -> str:
    sources = [x.strip() for x in str(existing or "").replace(";", "\n").splitlines() if x.strip()]
    if account_email.casefold() not in {x.casefold() for x in sources}:
        sources.append(account_email)
    return "\n".join(sources)


def _find_source_message(airtable: AirtableGold, source_key: str) -> dict | None:
    return (
        airtable.find_one("email", "Message ID sorgente", source_key)
        or airtable.find_one("email", "Gmail Message ID", source_key)
    )


def _register_duplicate_source(airtable: AirtableGold, sha: str, account_email: str) -> bool:
    existing = airtable.find_one("documenti", "SHA-256", sha)
    if not existing:
        return False
    fields = existing.get("fields", {})
    merged = _append_source(fields.get("Caselle origine", ""), account_email)
    if merged != str(fields.get("Caselle origine", "") or ""):
        airtable.update_record("documenti", existing["id"], {"Caselle origine": merged})
    return True


def sync_aruba_attachments(
    account_email: str,
    password: str,
    since: str | date | None = None,
    drive_folder_id: str | None = None,
    max_messages: int = 100,
    host: str = DEFAULT_IMAP_HOST,
    port: int = DEFAULT_IMAP_PORT,
) -> dict:
    """Read one Aruba mailbox, archive attachments and index them in Airtable.

    Mailboxes are independent sources. Messages are deduplicated by a stable
    source-specific key. Attachments are deduplicated globally by SHA-256 while
    all source mailboxes remain recorded on the single document record.
    """
    drive = build("drive", "v3", credentials=load_credentials(), cache_discovery=False)
    airtable = AirtableGold()
    client = _connect(account_email, password, host, port)
    result = {
        "account": account_email,
        "messages": 0,
        "attachments": 0,
        "uploaded": 0,
        "duplicates": 0,
        "duplicate_sources_updated": 0,
        "matched": 0,
        "archived_by_client": 0,
        "pending_review": 0,
        "errors": [],
    }

    try:
        status, _ = client.select("INBOX", readonly=True)
        if status != "OK":
            raise RuntimeError("Impossibile aprire INBOX.")

        status, data = client.uid("search", None, f'(SINCE "{_imap_since(since)}")')
        if status != "OK":
            raise RuntimeError("Ricerca IMAP non riuscita.")
        uids = [u for u in (data[0] or b"").split() if u]
        if max_messages > 0:
            uids = uids[-int(max_messages):]

        for uid in uids:
            uid_text = uid.decode("ascii", errors="ignore")
            try:
                status, payload = client.uid("fetch", uid, "(RFC822)")
                if status != "OK" or not payload or not payload[0]:
                    raise RuntimeError("Messaggio IMAP non leggibile.")
                raw_message = payload[0][1]
                msg = BytesParser(policy=policy.default).parsebytes(raw_message)
                result["messages"] += 1

                subject = str(msg.get("Subject") or "(senza oggetto)")
                sender_raw = str(msg.get("From") or "")
                sender_email = parseaddr(sender_raw)[1] or sender_raw
                message_id = str(msg.get("Message-ID") or "").strip()
                source_key = f"ARUBA:{account_email.casefold()}:{message_id or uid_text}"

                if _find_source_message(airtable, source_key):
                    result["duplicates"] += 1
                    continue

                body = _message_body(msg)
                context = f"{subject}\n{sender_raw}\n{body[:12000]}"
                email_match = match_client_practice(airtable, context)
                email_confident = bool(email_match.client_id and email_match.confidence >= 0.80)
                attachment_names: list[str] = []

                for part in msg.iter_attachments():
                    filename = str(part.get_filename() or "").strip()
                    if not filename:
                        continue
                    raw = part.get_payload(decode=True) or b""
                    if not raw:
                        continue
                    attachment_names.append(filename)
                    result["attachments"] += 1
                    sha = hashlib.sha256(raw).hexdigest()

                    if _register_duplicate_source(airtable, sha, account_email):
                        result["duplicates"] += 1
                        result["duplicate_sources_updated"] += 1
                        continue

                    extracted = _attachment_text(filename, part.get_content_type(), raw)
                    attachment_context = f"{filename}\n{context}\n{extracted}"
                    file_match = match_client_practice(airtable, attachment_context[:120000])
                    confident_client = bool(file_match.client_id and file_match.confidence >= 0.80)
                    if confident_client:
                        result["matched"] += 1

                    classification = classify_text(attachment_context[:120000])
                    ext = os.path.splitext(filename)[1] or ".bin"
                    if confident_client:
                        classification.company_name = file_match.client_name or ""
                    proposed = suggested_name(classification, extension=ext)

                    destination_id, archive_path = _archive_destination(
                        drive,
                        drive_folder_id,
                        file_match.client_name if confident_client else None,
                        classification.category,
                    )
                    media = MediaIoBaseUpload(
                        io.BytesIO(raw),
                        mimetype=part.get_content_type() or "application/octet-stream",
                        resumable=False,
                    )
                    saved = drive.files().create(
                        body={"name": proposed or filename, "parents": [destination_id]},
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
                        "Origine": "Altro",
                        "Caselle origine": account_email,
                        "URL Drive": saved.get("webViewLink", ""),
                        "SHA-256": sha,
                        "Stato Verifica": "Da verificare",
                        "Percorso nel pacchetto": f"EMAIL_ARUBA/{account_email}/{archive_path}",
                    }
                    if classification.document_year:
                        fields["Esercizio"] = int(classification.document_year)
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

                snippet = body.replace("\r", " ").replace("\n", " ")[:1500]
                email_fields = {
                    "Oggetto": subject,
                    "Mittente": sender_email,
                    "Casella origine": account_email,
                    "Message ID sorgente": source_key,
                    "Sintesi IA": snippet,
                    "Allegati": "\n".join(attachment_names),
                }
                msg_dt = _message_datetime(msg)
                if msg_dt:
                    email_fields["Data e ora"] = msg_dt
                if email_confident:
                    email_fields["Cliente"] = email_match.client_name or ""
                    email_fields["Cliente collegato"] = [email_match.client_id]
                if email_match.practice_id and email_confident:
                    email_fields["Pratica ID"] = email_match.practice_code or ""
                    email_fields["Pratica collegata"] = [email_match.practice_id]
                airtable.create_record("email", email_fields)

            except Exception as exc:
                result["errors"].append({"uid": uid_text, "error": str(exc)})
    finally:
        try:
            client.logout()
        except Exception:
            pass

    return result
