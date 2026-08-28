from __future__ import annotations
import csv, hashlib, io, mimetypes, os, re, zipfile
from pypdf import PdfReader
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from services.google_auth import load_credentials
from services.airtable_adapter import AirtableGold
from services.client_practice_matcher import match_client_practice

DOC_EXTS={'.pdf','.docx','.pptx','.xlsx','.xls','.xltx','.xml','.jpg','.jpeg','.png'}
CATEGORY_HINTS={
    'cr_banca_italia':'Centrale Rischi',
    'prospetti_bilancio':'Prospetto Bilancio',
    'bozze_bilancio':'Bozza Bilancio',
    'analitici_bilancio':'Bilancio Analitico',
    'presentazioni_aziendali':'Presentazione Aziendale',
    'bilanci_esercizio':'Bilancio di esercizio',
    'bilanci_gmail':'Bilancio',
}

def _norm(s:str)->str:
    return re.sub(r'[^a-z0-9]','',(s or '').casefold())

def _category(zip_name:str)->str:
    z=_norm(zip_name)
    for key,val in CATEGORY_HINTS.items():
        if _norm(key) in z:return val
    return 'Altro'

def _pdf_text(raw:bytes,max_pages:int=3)->str:
    try:
        r=PdfReader(io.BytesIO(raw)); parts=[]
        for p in r.pages[:max_pages]: parts.append(p.extract_text() or '')
        return '\n'.join(parts)[:20000]
    except Exception:return ''

def _year(text:str)->int|None:
    m=re.search(r'\b(20[0-3][0-9])\b',text or '')
    return int(m.group(1)) if m else None

def _ensure_folder(drive,name,parent=None):
    safe=name.replace("'","\\'")
    q=f"name='{safe}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent:q+=f" and '{parent}' in parents"
    hit=drive.files().list(q=q,spaces='drive',fields='files(id,name)',pageSize=1).execute().get('files',[])
    if hit:return hit[0]['id']
    body={'name':name,'mimeType':'application/vnd.google-apps.folder'}
    if parent:body['parents']=[parent]
    return drive.files().create(body=body,fields='id').execute()['id']

def _index_rows(z:zipfile.ZipFile)->dict[str,dict]:
    out={}
    for n in z.namelist():
        if not n.lower().endswith('.csv'):continue
        try:
            text=z.read(n).decode('utf-8-sig',errors='replace')
            delim=';' if text.count(';')>text.count(',') else ','
            for row in csv.DictReader(io.StringIO(text),delimiter=delim):
                filename=row.get('Nome file') or row.get('Nome_archivio') or row.get('File') or row.get('Nome_originale')
                if filename:
                    out[os.path.basename(filename)]={k:(v or '').strip() for k,v in row.items()}
        except Exception:pass
    return out

def import_zip_packages(zip_files,root_folder_id:str|None=None)->dict:
    airtable=AirtableGold(); drive=build('drive','v3',credentials=load_credentials(),cache_discovery=False)
    root=root_folder_id or os.getenv('GOOGLE_DRIVE_FOLDER_ID') or None
    result={'packages':0,'documents':0,'uploaded':0,'duplicates':0,'matched':0,'unmatched':0,'errors':[],'rows':[]}
    for uploaded in zip_files:
        result['packages']+=1
        zname=getattr(uploaded,'name','pacchetto.zip'); data=uploaded.getvalue() if hasattr(uploaded,'getvalue') else uploaded.read()
        try:z=zipfile.ZipFile(io.BytesIO(data))
        except Exception as exc:
            result['errors'].append(f'{zname}: ZIP non valido: {exc}');continue
        idx=_index_rows(z); category=_category(zname)
        for member in z.namelist():
            if member.endswith('/') or member.startswith('__MACOSX/'):continue
            base=os.path.basename(member); ext=os.path.splitext(base)[1].lower()
            if ext not in DOC_EXTS:continue
            result['documents']+=1
            try:
                raw=z.read(member); sha=hashlib.sha256(raw).hexdigest()
                if airtable.find_one('documenti','SHA-256',sha):
                    result['duplicates']+=1;continue
                meta=idx.get(base,{})
                company=meta.get('Azienda') or meta.get('Societa') or ''
                exercise=meta.get('Periodo/Esercizio') or meta.get('Esercizio') or ''
                doc_type=meta.get('Tipologia') or meta.get('Tipo_bilancio') or category
                context=' '.join([company,base,doc_type,exercise])
                if ext=='.pdf':context+=' '+_pdf_text(raw)
                match=match_client_practice(airtable,context)
                if match.client_id:result['matched']+=1
                else:result['unmatched']+=1
                client_name=match.client_name or company or 'DA_VERIFICARE'
                client_folder=_ensure_folder(drive,client_name,root)
                cat_folder=_ensure_folder(drive,category,client_folder)
                media=MediaIoBaseUpload(io.BytesIO(raw),mimetype=mimetypes.guess_type(base)[0] or 'application/octet-stream',resumable=False)
                saved=drive.files().create(body={'name':base,'parents':[cat_folder]},media_body=media,fields='id,name,webViewLink').execute()
                fields={'Documento':base,'Tipo Documento':doc_type or category,'Nome Originale':base,'Nome Definitivo':base,'Origine':'Import ZIP','URL Drive':saved.get('webViewLink',''),'SHA-256':sha,'Stato Verifica':'Verificato' if meta else 'Da verificare'}
                yr=_year(exercise or base)
                if yr:fields['Esercizio']=yr
                if match.client_id:
                    fields['Cliente']=match.client_name or client_name;fields['Cliente collegato']=[match.client_id]
                elif company:fields['Cliente']=company
                if match.practice_id:
                    fields['Pratica ID']=match.practice_code or '';fields['Pratica collegata']=[match.practice_id]
                airtable.create_record('documenti',fields);result['uploaded']+=1
                result['rows'].append({'zip':zname,'file':base,'cliente':client_name,'categoria':category,'stato':'ARCHIVIATO','drive':saved.get('webViewLink','')})
            except Exception as exc:
                result['errors'].append(f'{zname} / {base}: {exc}')
    return result
