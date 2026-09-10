from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


class PhotonError(RuntimeError):
    pass


@dataclass(frozen=True)
class PhotonConfig:
    client_id: str
    username: str
    api_key: str
    password: str
    secret_key: str
    environment: str = "sandbox"
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "PhotonConfig | None":
        values = {
            "client_id": os.getenv("PHOTON_CLIENT_ID", "").strip(),
            "username": os.getenv("PHOTON_USERNAME", "").strip(),
            "api_key": os.getenv("PHOTON_API_KEY", "").strip(),
            "password": os.getenv("PHOTON_PASSWORD", "").strip(),
            "secret_key": os.getenv("PHOTON_SECRET_KEY", "").strip(),
        }
        if not all(values.values()):
            return None
        return cls(
            **values,
            environment=os.getenv("PHOTON_ENV", "sandbox").strip().lower() or "sandbox",
            timeout_seconds=int(os.getenv("PHOTON_TIMEOUT_SECONDS", "60") or 60),
        )

    @property
    def base_url(self) -> str:
        if self.environment == "production":
            return "https://api.photoncommerce.com"
        return "https://sandbox-api.photoncommerce.com"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "CLIENT-ID": self.client_id,
            "AUTHORIZATION": f"apikey {self.username}:{self.api_key}",
            "PASSWORD": self.password,
            "SECRET-KEY": self.secret_key,
        }


class PhotonCommerceClient:
    """Small REST client following Photon's public PRO API examples."""

    def __init__(self, config: PhotonConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    def submit_bytes(self, data: bytes, filename: str, *, doctype: str) -> dict[str, Any]:
        if not data:
            raise PhotonError("Documento vuoto.")
        response = self.session.post(
            f"{self.config.base_url}/api/pro",
            headers=self.config.headers,
            params={"doctype": doctype},
            files={"pdf": (filename, data)},
            timeout=self.config.timeout_seconds,
        )
        self._raise(response, "Invio documento Photon")
        payload = response.json()
        photon_key = payload.get("photon_key") or (payload.get("data") or {}).get("photon_key")
        if not photon_key:
            if payload.get("data") or payload.get("result"):
                return payload
            raise PhotonError(f"Photon non ha restituito photon_key: {payload}")
        return {**payload, "photon_key": photon_key}

    def retrieve(self, photon_key: str) -> dict[str, Any]:
        response = self.session.get(
            f"{self.config.base_url}/api/v4/json",
            headers=self.config.headers,
            params={"photon_key": photon_key},
            timeout=self.config.timeout_seconds,
        )
        self._raise(response, "Recupero risultato Photon")
        return response.json()

    def process_bytes(
        self,
        data: bytes,
        filename: str,
        *,
        doctype: str,
        wait_seconds: float = 0.0,
        poll_interval: float = 2.0,
    ) -> dict[str, Any]:
        submitted = self.submit_bytes(data, filename, doctype=doctype)

        direct = submitted.get("data") or submitted.get("result")
        if isinstance(direct, dict) and direct.get("Document_Type"):
            return {"status": "extracted", "photon_key": submitted.get("photon_key", ""), "data": direct}

        key = str(submitted.get("photon_key") or "")
        if not key:
            raise PhotonError("Photon key assente.")
        if wait_seconds <= 0:
            return {"status": "queued", "photon_key": key, "data": {}}

        deadline = time.monotonic() + wait_seconds
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self.retrieve(key)
            data_obj = last.get("data") or last.get("result")
            if isinstance(data_obj, dict) and data_obj.get("Document_Type"):
                return {"status": "extracted", "photon_key": key, "data": data_obj}
            time.sleep(max(0.5, poll_interval))
        return {"status": "queued", "photon_key": key, "data": {}, "raw": last}

    @staticmethod
    def _raise(response: requests.Response, context: str) -> None:
        if response.ok:
            return
        body = response.text[:800]
        raise PhotonError(f"{context} fallito ({response.status_code}): {body}")


def photon_configured() -> bool:
    return PhotonConfig.from_env() is not None
