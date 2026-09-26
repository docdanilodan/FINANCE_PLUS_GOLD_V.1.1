from __future__ import annotations
import hashlib,hmac,json,os,re,secrets,time,unicodedata,urllib.request,urllib.error
from collections import defaultdict,deque
from contextlib import contextmanager
from typing import Any,Literal
import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI,Depends,Header,Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from pydantic import BaseModel,ConfigDict,Field
from starlette.middleware.trustedhost import TrustedHostMiddleware
from . import __version__

MASTER="SMART F+ aggiornato - Aruba e Coda"
EMAIL_RE=re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_{}|~-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}")
MODULES={"clienti":"clienti","i clienti":"clienti","tutti i clienti":"clienti","elenco clienti":"clienti","elenco dei clienti":"clienti","scheda clienti":"clienti","cliente 360":"cliente360","cliente360":"cliente360","documenti":"acquisizione","i documenti":"acquisizione","caricamento documenti":"acquisizione","acquisizione documenti":"acquisizione","integrazioni":"acquisizione"}
SYSTEM="""Sei SERAFINO 2.1 Cloud di SMART F+. Rispondi in italiano.
Usa solo i dati verificabili forniti dal database Neon. Non inventare score, DSCR,
rating, importi o documenti. Le simulazioni SMART F+ non sono delibere bancarie.
Le regole apprese sono PROPOSAL_ONLY: migliorano proposte e suggerimenti ma non
autorizzano modifiche critiche. Non dire di aver modificato o importato qualcosa
se il gateway non lo ha realmente fatto."""

class Fault(Exception):
    def __init__(self,status:int,code:str,message:str):
        super().__init__(message);self.status=status;self.code=code;self.message=message

def digest(v:str)->str:return hashlib.sha256(v.encode()).hexdigest()
def norm(v:str)->str:
    t=unicodedata.normalize("NFKD",str(v or ""))
    t="".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    return re.sub(r"\\s+"," ",re.sub(r"[^a-z0-9@._+ -]+"," ",t)).strip()
def money(v:Any)->str:
    if v in (None,""):return ""
    try:return f"{float(v):,.2f}".replace(",","X").replace(".",",").replace("X",".")+" EUR"
    except Exception:return str(v)

class Store:
    def __init__(self):
        self.url=(os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL") or "").strip()
        if not self.url:raise RuntimeError("DATABASE_URL non configurato")
    @contextmanager
    def conn(self):
        with psycopg.connect(self.url,connect_timeout=8,row_factory=dict_row) as c:yield c
    def ensure(self):
        ddl="""
        CREATE TABLE IF NOT EXISTS fp_mobile_devices_cloud(
          id TEXT PRIMARY KEY,label TEXT NOT NULL,secret_hash TEXT NOT NULL,scope_json JSONB,
          expires_at BIGINT NOT NULL,revoked BOOLEAN NOT NULL DEFAULT FALSE,created_at BIGINT NOT NULL,
          synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
        CREATE TABLE IF NOT EXISTS fp_mobile_sessions_cloud(
          token_hash TEXT PRIMARY KEY,device_id TEXT NOT NULL REFERENCES fp_mobile_devices_cloud(id),
          expires_at BIGINT NOT NULL,created_at BIGINT NOT NULL);
        CREATE TABLE IF NOT EXISTS fp_mobile_audit_cloud(
          id BIGSERIAL PRIMARY KEY,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          kind TEXT NOT NULL,device_id TEXT,target_id TEXT,result TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS fp_serafino_learning_rules_cloud(
          id BIGSERIAL PRIMARY KEY,source_rule_id BIGINT,rule_type TEXT NOT NULL,rule_key TEXT NOT NULL,
          payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,mode TEXT NOT NULL DEFAULT 'PROPOSAL_ONLY',
          uses INTEGER NOT NULL DEFAULT 0,confirmations INTEGER NOT NULL DEFAULT 0,
          contradictions INTEGER NOT NULL DEFAULT 0,active BOOLEAN NOT NULL DEFAULT TRUE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          source TEXT NOT NULL DEFAULT 'cloud',UNIQUE(rule_type,rule_key));
        """
        with self.conn() as c:
            with c.cursor() as cur:cur.execute(ddl)
            c.commit()
    def health(self):
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute("SELECT current_database() db,COUNT(*) n FROM clients");r=cur.fetchone()
        return {"ok":True,"database":r["db"],"clients":int(r["n"])}
    @staticmethod
    def scope(v):
        if v is None:return None
        if isinstance(v,str):
            try:v=json.loads(v)
            except Exception:return set()
        if not isinstance(v,list):return set()
        out=set()
        for x in v:
            try:out.add(int(x))
            except Exception:pass
        return out
    def session(self,device_id,device_secret):
        now=int(time.time())
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute("SELECT * FROM fp_mobile_devices_cloud WHERE id=%s",(device_id,));d=cur.fetchone()
                if not d or d["revoked"] or int(d["expires_at"])<=now:raise Fault(401,"DEVICE_UNAVAILABLE","Dispositivo non autorizzato o collegamento scaduto.")
                if not hmac.compare_digest(str(d["secret_hash"]),digest(device_secret)):raise Fault(401,"AUTH_FAILED","Credenziale dispositivo non valida.")
                token=secrets.token_urlsafe(32);exp=now+3600
                cur.execute("DELETE FROM fp_mobile_sessions_cloud WHERE device_id=%s OR expires_at<=%s",(device_id,now))
                cur.execute("INSERT INTO fp_mobile_sessions_cloud(token_hash,device_id,expires_at,created_at) VALUES(%s,%s,%s,%s)",(digest(token),device_id,exp,now))
                cur.execute("INSERT INTO fp_mobile_audit_cloud(kind,device_id,target_id,result) VALUES('SESSION',%s,NULL,'OK')",(device_id,))
            c.commit()
        return {"access_token":token,"expires_in":3600}
    def identity(self,token):
        now=int(time.time())
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute("""SELECT d.id,d.label,d.scope_json,d.expires_at,d.revoked,s.expires_at session_expires
                FROM fp_mobile_sessions_cloud s JOIN fp_mobile_devices_cloud d ON d.id=s.device_id
                WHERE s.token_hash=%s""",(digest(token),));d=cur.fetchone()
        if not d or d["revoked"] or int(d["expires_at"])<=now or int(d["session_expires"])<=now:raise Fault(401,"AUTH_REQUIRED","Sessione scaduta.")
        d=dict(d);d["scope"]=self.scope(d.get("scope_json"));return d
    @staticmethod
    def require_client(cid,scope):
        if scope is not None and cid not in scope:raise Fault(404,"CLIENT_NOT_FOUND","Cliente non disponibile.")
    def audit(self,kind,device,target,result):
        try:
            with self.conn() as c:
                with c.cursor() as cur:cur.execute("INSERT INTO fp_mobile_audit_cloud(kind,device_id,target_id,result) VALUES(%s,%s,%s,%s)",(kind[:80],device,target,result[:120]))
                c.commit()
        except Exception:pass
    def count(self,table,col,scope):
        if scope is not None and not scope:return 0
        with self.conn() as c:
            with c.cursor() as cur:
                if scope is None:cur.execute(f"SELECT COUNT(*) n FROM {table}")
                else:cur.execute(f"SELECT COUNT(*) n FROM {table} WHERE {col}=ANY(%s)",(list(scope),))
                return int(cur.fetchone()["n"])
    def dashboard(self,scope):
        return {"clients":self.count("clients","id",scope),"documents":self.count("documents","client_id",scope),
        "requests":self.count("practices","client_id",scope),"pending_mobile":0,
        "master_name":MASTER+" / Neon Cloud","read_at":int(time.time())}
    def clients(self,scope,q=""):
        clauses=[];params=[]
        if scope is not None:
            if not scope:return []
            clauses.append("id=ANY(%s)");params.append(list(scope))
        if q:
            clauses.append("(legal_name ILIKE %s OR COALESCE(vat,'') ILIKE %s)");like="%"+q+"%";params += [like,like]
        where=(" WHERE "+" AND ".join(clauses)) if clauses else ""
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute("SELECT id,legal_name,COALESCE(vat,'') vat,COALESCE(ateco,'') ateco,COALESCE(legal_form,'') legal_form FROM clients"+where+" ORDER BY legal_name LIMIT 500",params);rows=cur.fetchall()
        return [{"id":int(r["id"]),"name":r["legal_name"] or "","vat":r["vat"] or "","sector":" · ".join(x for x in (r["ateco"],r["legal_form"]) if x)} for r in rows]
    def find_client(self,q,scope):
        rows=self.clients(scope,q);k=q.strip().casefold();exact=[r for r in rows if r["name"].strip().casefold()==k]
        if len(exact)==1:return exact[0],rows
        if len(rows)==1:return rows[0],rows
        return None,rows[:5]
    def bundle(self,cid,scope):
        self.require_client(cid,scope)
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute("SELECT id,legal_name,COALESCE(vat,'') vat,COALESCE(ateco,'') ateco,COALESCE(legal_form,'') legal_form FROM clients WHERE id=%s",(cid,));cl=cur.fetchone()
                if not cl:raise Fault(404,"CLIENT_NOT_FOUND","Cliente non disponibile.")
                cur.execute("""SELECT id,client_id,COALESCE(canonical_name,original_name,'Documento') title,COALESCE(category,'Altro') category,
                COALESCE(document_date::text,created_at::date::text,'') date FROM documents WHERE client_id=%s ORDER BY created_at DESC,id DESC LIMIT 200""",(cid,));docs=cur.fetchall()
                cur.execute("""SELECT id,COALESCE(NULLIF(practice_type,''),NULLIF(code,''),'Pratica') title,COALESCE(status,'') status,
                requested_amount,COALESCE(next_action,'') next_action,COALESCE(missing_documents,'') missing_documents
                FROM practices WHERE client_id=%s ORDER BY created_at DESC,id DESC LIMIT 100""",(cid,));reqs=cur.fetchall()
                cur.execute("SELECT analysis_type,data_quality,score,rating,result_json FROM analyses WHERE client_id=%s ORDER BY created_at DESC,id DESC LIMIT 1",(cid,));an=cur.fetchone()
        analysis=None
        if an:
            extra=an["result_json"] if isinstance(an["result_json"],dict) else {}
            analysis={"engine_version":an["analysis_type"] or "SMART F+","score":an["score"],"score_band":an["rating"],"debt_capacity":extra.get("debt_capacity"),"data_quality":an["data_quality"]}
        return {"client":{"id":int(cl["id"]),"name":cl["legal_name"] or "","vat":cl["vat"] or "","sector":" · ".join(x for x in (cl["ateco"],cl["legal_form"]) if x)},
        "documents":[{"id":int(r["id"]),"client_id":int(r["client_id"]),"title":r["title"],"category":r["category"],"date":r["date"]} for r in docs],
        "requests":[{"id":int(r["id"]),"title":r["title"],"status":r["status"],"amount":money(r["requested_amount"]),"next_action":r["next_action"],"missing_documents":r["missing_documents"]} for r in reqs],
        "tasks":[],"analysis":analysis,"notes":[],"source":"Neon PostgreSQL / FinancePlus Cloud","read_at":int(time.time())}
    def rules(self,limit=30):
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute("SELECT * FROM fp_serafino_learning_rules_cloud WHERE active=TRUE ORDER BY updated_at DESC,id DESC LIMIT %s",(limit,));return [dict(r) for r in cur.fetchall()]
    def learn(self,typ,key,payload):
        with self.conn() as c:
            with c.cursor() as cur:
                cur.execute("""INSERT INTO fp_serafino_learning_rules_cloud(rule_type,rule_key,payload_json,uses,confirmations,active,source)
                VALUES(%s,%s,%s::jsonb,1,1,TRUE,'cloud') ON CONFLICT(rule_type,rule_key) DO UPDATE SET
                payload_json=EXCLUDED.payload_json,uses=fp_serafino_learning_rules_cloud.uses+1,
                confirmations=fp_serafino_learning_rules_cloud.confirmations+1,active=TRUE,updated_at=NOW(),source='cloud'""",(typ,key,json.dumps(payload,ensure_ascii=False)))
            c.commit()
    def context(self,cid,scope):
        rules=[{"type":r["rule_type"],"key":r["rule_key"],"payload":r["payload_json"]} for r in self.rules()]
        if cid is None:return {"notice":"Nessun cliente selezionato.","learning_rules":rules}
        b=self.bundle(cid,scope);return {"client":b["client"],"documents":b["documents"][:40],"practices":b["requests"][:20],"analysis":b["analysis"],"learning_rules":rules,"source":b["source"]}

class Mistral:
    def __init__(self):self.key=(os.getenv("MISTRAL_API_KEY") or "").strip();self.model=(os.getenv("MISTRAL_MODEL") or "mistral-small-latest").strip()
    def reply(self,messages,context):
        if not self.key:raise Fault(503,"AI_NOT_CONFIGURED","SERAFINO cloud non ha ancora il provider AI configurato.")
        packed=json.dumps(context,ensure_ascii=False,separators=(",",":"))[:60000]
        body={"model":self.model,"temperature":0.2,"max_tokens":900,"messages":[{"role":"system","content":SYSTEM+"\\nCONTESTO JSON:\\n"+packed}]+messages[-10:]}
        req=urllib.request.Request("https://api.mistral.ai/v1/chat/completions",data=json.dumps(body).encode(),headers={"Authorization":"Bearer "+self.key,"Content-Type":"application/json"},method="POST")
        try:
            with urllib.request.urlopen(req,timeout=75) as r:data=json.loads(r.read(300000))
            return str(data["choices"][0]["message"]["content"]).strip()
        except Exception:raise Fault(503,"AI_PROVIDER_ERROR","SERAFINO cloud non ha completato la risposta.") from None

try:
    store=Store();store.ensure()
except Exception:
    store=None
ai=Mistral()
app=FastAPI(title="SMART F+ Mobile Cloud",version=__version__,docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=[x.strip() for x in (os.getenv("ALLOWED_HOSTS") or "*.onrender.com,localhost,127.0.0.1").split(",") if x.strip()])
bearer=HTTPBearer(auto_error=False)
events=defaultdict(deque);lock=__import__("threading").Lock()
def rate(key,limit):
    now=time.monotonic()
    with lock:
        q=events[key]
        while q and q[0]<now-60:q.popleft()
        if len(q)>=limit:raise Fault(429,"RATE_LIMIT","Attendi un minuto prima di riprovare.")
        q.append(now)

class Strict(BaseModel):model_config=ConfigDict(extra="forbid")
class SessionInput(Strict):device_id:str=Field(min_length=36,max_length=36);device_secret:str=Field(min_length=32,max_length=256)
class Message(Strict):role:Literal["user","assistant"];content:str=Field(min_length=1,max_length=6000)
class ChatInput(Strict):client_id:int|None=Field(default=None,gt=0,strict=True);messages:list[Message]=Field(min_length=1,max_length=12)

@app.exception_handler(Fault)
async def fault_handler(request,exc):return JSONResponse({"code":exc.code,"message":exc.message},status_code=exc.status)
@app.exception_handler(RequestValidationError)
async def validation_handler(request,exc):return JSONResponse({"code":"INVALID_REQUEST","message":"Parametri non validi."},status_code=422)
@app.exception_handler(Exception)
async def unexpected_handler(request,exc):return JSONResponse({"code":"INTERNAL_ERROR","message":"Operazione cloud non completata."},status_code=500)
@app.middleware("http")
async def transport(request,call_next):
    if request.headers.get("origin") or request.headers.get("content-encoding"):return JSONResponse({"code":"TRANSPORT_REJECTED","message":"Richiesta non consentita."},status_code=403)
    r=await call_next(request);r.headers["Cache-Control"]="no-store";r.headers["X-Content-Type-Options"]="nosniff";return r
def require_store():
    if store is None: raise Fault(503,"DATABASE_NOT_CONFIGURED","Configura DATABASE_URL del progetto Neon FinancePlus Cloud.")
    return store
def identity(credentials:HTTPAuthorizationCredentials|None=Depends(bearer)):
    s=require_store()
    if not credentials or credentials.scheme.lower()!="bearer":raise Fault(401,"AUTH_REQUIRED","Collega e sblocca il dispositivo.")
    d=s.identity(credentials.credentials);rate("device:"+d["id"],180);return d

@app.get("/health")
def health():
    if store is None:return {"service":"SMART F+ Mobile Cloud","version":__version__,"database_ready":False,"clients":0,"serafino_ai":"READY" if ai.key else "NOT_CONFIGURED","requires_pc_online":False}
    h=store.health();return {"service":"SMART F+ Mobile Cloud","version":__version__,"database_ready":True,"clients":h["clients"],"serafino_ai":"READY" if ai.key else "NOT_CONFIGURED","requires_pc_online":False}
@app.post("/v1/session")
def new_session(body:SessionInput,request:Request):rate("auth:"+str(request.client.host if request.client else "unknown"),12);return require_store().session(body.device_id,body.device_secret)
@app.get("/v1/capabilities")
def capabilities(d=Depends(identity)):return {"version":__version__,"master":MASTER,"read":True,"intake":False,"approval_queue":False,"ai_provider":"mistral","ai_configured":bool(ai.key),"push":False,"cloud_sync":True,"requires_pc_online":False,"voice":"ios_on_device_push_to_talk","serafino_operator":True,"serafino_version":"2.1-cloud","navigation_commands":True,"learning":True,"material_actions_require_confirmation":True,"cloud_binary_storage":False}
@app.get("/v1/dashboard")
def dashboard(d=Depends(identity)):return store.dashboard(d["scope"])
@app.get("/v1/clients")
def clients(q:str="",d=Depends(identity)):return {"items":store.clients(d["scope"],q),"limit":500}
@app.get("/v1/clients/{cid}")
def client(cid:int,d=Depends(identity)):return store.bundle(cid,d["scope"])
@app.get("/v1/documents/{ident}/content")
def document(ident:int,d=Depends(identity)):raise Fault(409,"DOCUMENT_BINARY_NOT_CLOUD","Il metadato e nel cloud, ma il file fisico non e ancora nello storage privato cloud.")
@app.get("/v1/intakes")
def intakes(d=Depends(identity)):return {"items":[]}
@app.post("/v1/intakes")
def upload(request:Request,d=Depends(identity),x_filename:str=Header(default=""),x_idempotency_key:str=Header(default="")):raise Fault(503,"CLOUD_STORAGE_REQUIRED","Caricamento cloud non ancora attivo: serve storage privato permanente.")
@app.post("/v1/intakes/{ident}/approve")
def approve(ident:str,d=Depends(identity)):raise Fault(409,"NO_CLOUD_INTAKE","Nessuna acquisizione cloud da approvare.")

def reply(text,mode,navigation=None,notice="Nessuna modifica critica eseguita.",source="SMART F+ / SERAFINO 2.1 Cloud"):
    return {"text":text,"provider":"smartfplus-serafino-cloud","prompt_version":"serafino-cloud-2.1","source":source,"mode":mode,"navigation":navigation,"requires_confirmation":False,"confirmation_title":None,"operator_result":None,"notice":notice}
@app.post("/v1/serafino/chat")
def chat(body:ChatInput,d=Depends(identity)):
    rate("chat:"+d["id"],12);raw=body.messages[-1].content;q=norm(raw);scope=d["scope"]
    if body.client_id is not None:store.require_client(body.client_id,scope)
    z=q[9:].strip() if q.startswith("serafino ") else q
    if z.startswith("apri "):
        target=z[5:].strip()
        if target in MODULES:
            out=reply("Apro "+target+".","SERAFINO_OPERATORE",{"module":MODULES[target],"client_id":body.client_id})
        else:
            original=raw.strip()
            if norm(original).startswith("serafino "):
                original=original.split(" ",1)[1].strip()
            if norm(original).startswith("apri "):
                original=original.split(" ",1)[1].strip()
            if norm(original).startswith("cliente ") and " " in original:
                original=original.split(" ",1)[1].strip()
            cl,cands=store.find_client(original,scope)
            if cl:out=reply("Apro Cliente 360 di "+cl["name"]+".","SERAFINO_OPERATORE",{"module":"cliente360","client_id":cl["id"]},source="Neon PostgreSQL / Cliente 360")
            else:out=reply("Cliente non identificato in modo univoco."+(" Possibili corrispondenze: "+", ".join(x["name"] for x in cands) if cands else ""),"SERAFINO_OPERATORE")
    elif any(phrase in z for phrase in (
        "quanti clienti sono disponibili",
        "quanti clienti risultano disponibili",
        "quanti clienti ci sono",
        "numero clienti",
        "conteggio clienti",
    )):
        n=store.count("clients","id",scope)
        out=reply(f"Nel cloud Neon risultano disponibili {n} clienti.","SERAFINO_OPERATORE",source="Neon PostgreSQL / FinancePlus Cloud")
    elif q in {"cosa hai imparato","mostra regole","mostra cosa hai imparato","regole apprese"}:
        rs=store.rules();lines=[r["rule_type"]+": "+r["rule_key"] for r in rs];out=reply("Regole apprese attive:\\n- "+"\\n- ".join(lines) if lines else "Non ho ancora regole apprese attive nel cloud.","SERAFINO_LEARNING")
    else:
        m=re.search(r"quest[oa](?: documento)? e (?:un |una )?(.+?) non (.+)$",q)
        if m and scope is None:
            new=m.group(1).strip(" ,.");old=m.group(2).strip(" ,.");store.learn("document_classification",norm(old)+">"+norm(new),{"old_category":old,"new_category":new,"mode":"PROPOSAL_ONLY"});out=reply(f"Correzione appresa: {old} -> {new}. La usero nelle prossime proposte senza modificare documenti gia archiviati.","SERAFINO_LEARNING",notice="Regola PROPOSAL_ONLY salvata su Neon.")
        elif EMAIL_RE.search(raw) and any(x in q for x in ("carica","scarica","importa","prendi")) and any(x in q for x in ("pdf","allegat","mail","email")):
            out=reply("Il comando e riconosciuto, ma i file binari non sono ancora nello storage cloud privato. Non importo nulla.","SERAFINO_CLOUD_STORAGE_REQUIRED",notice="Nessuna acquisizione eseguita.",source="SMART F+ / Cloud Storage Gate")
        else:
            text=ai.reply([m.model_dump() for m in body.messages],store.context(body.client_id,scope));out=reply(text,"SERAFINO_CLOUD_MISTRAL",notice="Risposta AI basata sui dati cloud disponibili; nessuna azione materiale eseguita.",source="Neon PostgreSQL / SERAFINO Cloud")
    store.audit("SERAFINO_CLOUD",d["id"],str(body.client_id) if body.client_id else None,out["mode"]);out["client_id"]=body.client_id;return out
