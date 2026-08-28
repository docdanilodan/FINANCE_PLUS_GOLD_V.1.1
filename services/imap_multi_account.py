from __future__ import annotations
import email, hashlib, imaplib, io, mimetypes, os, ssl
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from services.google_auth import load_credentials
from services.airtable_adapter import AirtableGold
from services.client_practice_matcher import match_client_practice
from document_ai import classify_text, suggested_name

ACCOUNTS = {
    "D.Dangelo@financeplus.tech": {
        "host_env": "FP_DDANGELO_IMAP_HOST", "port_env": "FP_DDANGELO_IMAP_PORT",
        "user_env": "FP_DDANGELO_IMAP_USER", "password_env": "FP_DDANGELO_IMAP_PASSWORD",
    },
    "Pratiche@financeplus.tech": {
        "host_env": "FP_PRATICHE_IMAP_HOST", "port_env": "FP_PRATICHE_IMAP_PORT",
        "user_env": "FP_PRATICHE_IMAP_USER", "password_env": "FP_PRATICHE_IMAP_PASSWORD",
    },
}

def _text(v):
    try:return str(make_header(decode_header(v or "")))
    except Exception:return str(v or "")

def _body(msg):
    parts=[]
    for p in msg.walk():
        if p.get_content_maintype()=="multipart" or p.get_filename():continue
        if p.get_content_type() not in ("text/plain","text/html"):continue
        try:parts.append(p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8",errors="replace"))
        except Exception:pass
    return "\n".join(parts)[:30000]

def _attachments(msg):
    for p in msg.walk():
        name=_text(p.get_filename())
        raw=p.get_payload(decode=True)
        if name and raw:yield name,raw,p.get_content_type()

def _message_key(account,mailbox,uid):
    return f"IMAP:{account}:{mailbox}:{uid}"

def _ensure_folder(drive,name,parent=None):
    safe=name.replace("'","\\'")
    q=f"name='{safe}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent:q+=f" and '{parent}' in parents"
    hit=drive.files().list(q=q,spaces='drive',fields='files(id)',pageSize=1).execute().get('files',[])
    if hit:return hit[0]['id']
    meta={'name':name,'mimeType':'application/vnd.google-apps.folder'}
    if parent:meta['parents']=[parent]
    return drive.files().create(body=meta,fields='id').execute()['id']

def sync_imap_account(account:str, mailbox:str="INBOX", since:str|None=None, max_messages:int=250, root_folder_id:str|None=None)->dict:
    cfg=ACCOUNTS[account]
    host=os.getenv(cfg['host_env'],""); port=int(os.getenv(cfg['port_env'],"993")); user=os.getenv(cfg['user_env'],account); password=os.getenv(cfg['password_env'],"")
    if not host or not password:raise RuntimeError(f"Secrets IMAP non configurati per {account}")
    airtable=AirtableGold(); drive=build('drive','v3',credentials=load_credentials(),cache_discovery=False)
    root=root_folder_id or os.getenv('GOOGLE_DRIVE_FOLDER_ID') or None
    result={'account':account,'messages':0,'attachments':0,'uploaded':0,'duplicates':0,'matched_clients':0,'errors':[]}
    with imaplib.IMAP4_SSL(host,port,ssl_context=ssl.create_default_context()) as imap:
        imap.login(user,password); imap.select(mailbox,readonly=True)
        criteria=f'(SINCE {since})' if since else 'ALL'
        status,data=imap.uid('search',None,criteria)
        if status!='OK':return result
        uids=data[0].split()[-max_messages:]
        for uidb in uids:
            uid=uidb.decode(); key=_message_key(account,mailbox,uid)
            try:
                if airtable.find_one('email','Gmail Message ID',key):result['duplicates']+=1;continue
                status,payload=imap.uid('fetch',uid,'(RFC822)')
                if status!='OK':continue
                raw_msg=next(x[1] for x in payload if isinstance(x,tuple)); msg=email.message_from_bytes(raw_msg)
                subject=_text(msg.get('Subject')); sender=parseaddr(_text(msg.get('From')))[1]; body=_body(msg); names=[n for n,_,_ in _attachments(msg)]
                match=match_client_practice(airtable,' '.join([subject,sender,body]+names))
                if match.client_id:result['matched_clients']+=1
                client_ids=[match.client_id] if match.client_id else []; practice_ids=[match.practice_id] if match.practice_id else []
                for filename,raw,mime in _attachments(msg):
                    result['attachments']+=1; sha=hashlib.sha256(raw).hexdigest()
                    if airtable.find_one('documenti','SHA-256',sha):result['duplicates']+=1;continue
                    classification=classify_text(filename+' '+body[:5000]); ext=os.path.splitext(filename)[1] or '.bin'; final_name=suggested_name(classification,extension=ext) or filename
                    parent=root
                    if match.client_name:parent=_ensure_folder(drive,match.client_name,root)
                    media=MediaIoBaseUpload(io.BytesIO(raw),mimetype=mime or mimetypes.guess_type(filename)[0] or 'application/octet-stream',resumable=False)
                    meta={'name':final_name};
                    if parent:meta['parents']=[parent]
                    saved=drive.files().create(body=meta,media_body=media,fields='id,name,webViewLink').execute()
                    fields={'Documento':saved['name'],'Tipo Documento':classification.category,'Nome Originale':filename,'Nome IA Suggerito':final_name,'Nome Definitivo':final_name,'Origine':'Email','URL Drive':saved.get('webViewLink',''),'SHA-256':sha,'Stato Verifica':'Da verificare','Casella sorgente':account}
                    if match.client_id:fields['Cliente collegato']=[match.client_id];fields['Cliente']=match.client_name or ''
                    if match.practice_id:fields['Pratica collegata']=[match.practice_id];fields['Pratica ID']=match.practice_code or ''
                    airtable.create_record('documenti',fields);result['uploaded']+=1
                email_fields={'Oggetto':subject,'Mittente':sender,'Gmail Message ID':key,'Casella sorgente':account,'Allegati':'\n'.join(names)}
                try:email_fields['Data e ora']=parsedate_to_datetime(msg.get('Date')).isoformat()
                except Exception:pass
                if match.client_id:email_fields['Cliente collegato']=[match.client_id];email_fields['Cliente']=match.client_name or ''
                if match.practice_id:email_fields['Pratica collegata']=[match.practice_id];email_fields['Pratica ID']=match.practice_code or ''
                airtable.create_record('email',email_fields);result['messages']+=1
            except Exception as exc:result['errors'].append({'uid':uid,'error':str(exc)})
    return result

def sync_financeplus_mailboxes(**kwargs)->dict:
    return {account:sync_imap_account(account,**kwargs) for account in ACCOUNTS}
