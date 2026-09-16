from __future__ import annotations
from abc import ABC, abstractmethod
from hashlib import sha256
from pathlib import Path

class StoragePort(ABC):
    @abstractmethod
    def put(self, data: bytes, name: str, *, sha: str | None = None) -> str: ...

class LocalStorage(StoragePort):
    def __init__(self, root: str | Path="financeplus_data/documents"):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def put(self,data:bytes,name:str,*,sha:str|None=None)->str:
        digest=sha or sha256(data).hexdigest(); suffix=Path(name).suffix.lower(); target=self.root/digest[:2]/f"{digest}{suffix}"; target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists(): target.write_bytes(data)
        return target.resolve().as_uri()

class GoogleDriveStorage(StoragePort):
    def put(self,data:bytes,name:str,*,sha:str|None=None)->str:
        raise RuntimeError("RICHIEDE CREDENZIALI: usare adapter Drive corrente dietro StoragePort nel deploy.")

class OneDriveStorage(StoragePort):
    def put(self,data:bytes,name:str,*,sha:str|None=None)->str:
        raise RuntimeError("DA TESTARE / RICHIEDE CREDENZIALI: adapter OneDrive non presente nelle fonti verificate.")
