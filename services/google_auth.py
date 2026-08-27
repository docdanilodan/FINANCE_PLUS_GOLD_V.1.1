from __future__ import annotations
import json, os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/drive.file',
]

def load_credentials() -> Credentials:
    raw = os.getenv('GOOGLE_OAUTH_TOKEN_JSON', '').strip()
    if not raw:
        raise RuntimeError('GOOGLE_OAUTH_TOKEN_JSON non configurato')
    info = json.loads(raw)
    creds = Credentials.from_authorized_user_info(info, scopes=SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds.valid:
        raise RuntimeError('Credenziali Google non valide o scope insufficienti')
    return creds
