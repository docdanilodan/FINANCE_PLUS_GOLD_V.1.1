from __future__ import annotations
from hashlib import sha256
from pathlib import Path
from financeplus.audit import audit


def ingest_document(session, repository, storage, *, data: bytes, filename: str, client_id: int | None = None, practice_id: int | None = None, category: str = "Altro", source_channel: str = "manuale", actor: str = "system"):
    digest=sha256(data).hexdigest()
    uri=storage.put(data, filename, sha=digest)
    row, created=repository.create_document(client_id=client_id,practice_id=practice_id,category=category,original_name=filename,canonical_name=Path(filename).name,sha256=digest,storage_uri=uri,source_channel=source_channel,verification_status="DA_VERIFICARE",metadata_json={})
    audit(session,"DOCUMENT_INGEST" if created else "DOCUMENT_DEDUP",actor=actor,entity_type="document",entity_id=row.id,detail={"sha256":digest,"source_channel":source_channel,"filename":filename})
    return row, created
