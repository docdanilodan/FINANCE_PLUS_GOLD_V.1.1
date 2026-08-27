from __future__ import annotations
import base64, hashlib, io, os
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from services.google_auth import load_credentials
from services.airtable_adapter import AirtableGold
from document_ai import classify_text, suggested_name


def _walk(parts):
    for p in parts or []:
        yield p
        yield from _walk(p.get('parts', []))


def _already_indexed(airtable: AirtableGold, table: str, field: str, value: str) -> bool:
    if not value:
        return False
    try:
        return bool(airtable.list_records(table, formula=f"{{{field}}}='{value}'", max_records=1))
    except Exception:
        return False


def sync_gmail_attachments(query: str = 'has:attachment newer_than:1d -in:spam -in:trash', drive_folder_id: str | None = None, max_messages: int = 50) -> dict:
    creds = load_credentials()
    gmail = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    drive = build('drive', 'v3', credentials=creds, cache_discovery=False)
    airtable = AirtableGold()
    result = {'messages': 0, 'attachments': 0, 'uploaded': 0, 'duplicates': 0, 'errors': []}
    ids = gmail.users().messages().list(userId='me', q=query, maxResults=max_messages).execute().get('messages', [])
    for item in ids:
        try:
            msg = gmail.users().messages().get(userId='me', id=item['id'], format='full').execute()
            result['messages'] += 1
            headers = {h['name'].lower(): h['value'] for h in msg['payload'].get('headers', [])}
            if _already_indexed(airtable, 'email', 'Gmail Message ID', msg['id']):
                result['duplicates'] += 1
                continue
            for part in _walk(msg['payload'].get('parts', [])):
                filename = part.get('filename', '')
                aid = part.get('body', {}).get('attachmentId')
                if not filename or not aid:
                    continue
                result['attachments'] += 1
                data = gmail.users().messages().attachments().get(userId='me', messageId=msg['id'], id=aid).execute()['data']
                raw = base64.urlsafe_b64decode(data + '===')
                sha = hashlib.sha256(raw).hexdigest()
                if _already_indexed(airtable, 'documenti', 'SHA-256', sha):
                    result['duplicates'] += 1
                    continue
                # Safety: filename-only classification is provisional. Binary content must be extracted/OCR'd before verification.
                classification = classify_text(filename)
                ext = ''.join(os.path.splitext(filename)[1:]) or '.bin'
                proposed = suggested_name(classification, extension=ext)
                media = MediaIoBaseUpload(io.BytesIO(raw), mimetype=part.get('mimeType') or 'application/octet-stream', resumable=False)
                meta = {'name': proposed or filename}
                if drive_folder_id:
                    meta['parents'] = [drive_folder_id]
                saved = drive.files().create(body=meta, media_body=media, fields='id,webViewLink,name').execute()
                result['uploaded'] += 1
                airtable.create_record('documenti', {
                    'Documento': saved['name'], 'Tipo Documento': classification.category,
                    'Nome Originale': filename, 'Nome IA Suggerito': saved['name'],
                    'Nome Definitivo': saved['name'], 'Origine': 'Gmail',
                    'URL Drive': saved.get('webViewLink', ''), 'SHA-256': sha,
                    'Stato Verifica': 'Da verificare'
                })
            airtable.create_record('email', {
                'Oggetto': headers.get('subject', '(senza oggetto)'),
                'Mittente': headers.get('from', ''),
                'Gmail Message ID': msg['id']
            })
        except Exception as e:
            result['errors'].append({'message_id': item.get('id'), 'error': str(e)})
    return result
