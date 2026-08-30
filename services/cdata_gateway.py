from __future__ import annotations

import base64
import os
from typing import Any, Dict

import requests


class CDataGateway:
    """Read-oriented CData Connect AI gateway.

    FinancePlus keeps CData credentials in the deployment secret store. The
    gateway is intentionally generic so new real data sources can be added in
    CData without changing the event orchestrator.
    """

    def __init__(
        self,
        user: str | None = None,
        pat: str | None = None,
        base_url: str | None = None,
    ):
        self.user = user or os.getenv("CDATA_USER", "")
        self.pat = pat or os.getenv("CDATA_PAT", "")
        self.base_url = (base_url or os.getenv("CDATA_BASE_URL", "https://cloud.cdata.com")).rstrip("/")
        if not self.user or not self.pat:
            raise RuntimeError("CDATA_USER / CDATA_PAT non configurati")

    def _headers(self) -> Dict[str, str]:
        token = base64.b64encode(f"{self.user}:{self.pat}".encode("utf-8")).decode("ascii")
        return {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

    def query(self, sql: str) -> Any:
        if not sql.lstrip().upper().startswith("SELECT"):
            raise ValueError("FinancePlus CDataGateway consente solo SELECT")
        response = requests.post(
            f"{self.base_url}/api/query",
            headers=self._headers(),
            json={"query": sql},
            timeout=90,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return response.json()
        return response.text

    def healthcheck(self) -> Dict[str, Any]:
        return {
            "configured": bool(self.user and self.pat),
            "base_url": self.base_url,
        }
