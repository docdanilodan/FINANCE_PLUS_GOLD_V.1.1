from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests


class AzureDocumentIntelligenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class AzureDocumentIntelligenceConfig:
    endpoint: str
    key: str
    api_version: str = "2024-11-30"
    model_id: str = "prebuilt-layout"
    timeout_seconds: int = 90
    poll_interval_seconds: float = 1.0

    @classmethod
    def from_env(cls) -> "AzureDocumentIntelligenceConfig | None":
        endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "").strip().rstrip("/")
        key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "").strip()
        if not endpoint or not key:
            return None
        return cls(
            endpoint=endpoint,
            key=key,
            api_version=os.getenv(
                "AZURE_DOCUMENT_INTELLIGENCE_API_VERSION",
                "2024-11-30",
            ).strip()
            or "2024-11-30",
            model_id=os.getenv(
                "AZURE_DOCUMENT_INTELLIGENCE_MODEL",
                "prebuilt-layout",
            ).strip()
            or "prebuilt-layout",
            timeout_seconds=int(
                os.getenv("AZURE_DOCUMENT_INTELLIGENCE_TIMEOUT_SECONDS", "90") or 90
            ),
            poll_interval_seconds=float(
                os.getenv("AZURE_DOCUMENT_INTELLIGENCE_POLL_SECONDS", "1") or 1
            ),
        )


class AzureDocumentIntelligenceClient:
    """Minimal REST adapter for Azure AI Document Intelligence.

    The adapter deliberately has no knowledge of FinancePlus UI or business
    logic. Privacy gating is handled by the caller before bytes are submitted.
    """

    def __init__(
        self,
        config: AzureDocumentIntelligenceConfig,
        session: requests.Session | None = None,
    ):
        self.config = config
        self.session = session or requests.Session()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Ocp-Apim-Subscription-Key": self.config.key,
            "Content-Type": "application/octet-stream",
        }

    def analyze_bytes(self, raw: bytes) -> str:
        if not raw:
            raise AzureDocumentIntelligenceError("Documento vuoto.")

        url = (
            f"{self.config.endpoint}/documentintelligence/documentModels/"
            f"{self.config.model_id}:analyze"
        )
        response = self.session.post(
            url,
            params={
                "api-version": self.config.api_version,
                "outputContentFormat": "markdown",
            },
            headers=self._headers,
            data=raw,
            timeout=self.config.timeout_seconds,
        )

        if response.status_code == 200:
            return self._extract_content(response.json())

        if response.status_code != 202:
            body = response.text[:800]
            raise AzureDocumentIntelligenceError(
                f"Azure Document Intelligence analyze fallito "
                f"({response.status_code}): {body}"
            )

        operation_url = response.headers.get("operation-location", "").strip()
        if not operation_url:
            raise AzureDocumentIntelligenceError(
                "Azure Document Intelligence non ha restituito operation-location."
            )

        deadline = time.monotonic() + self.config.timeout_seconds
        poll_headers = {"Ocp-Apim-Subscription-Key": self.config.key}
        while time.monotonic() < deadline:
            polled = self.session.get(
                operation_url,
                headers=poll_headers,
                timeout=self.config.timeout_seconds,
            )
            if not polled.ok:
                raise AzureDocumentIntelligenceError(
                    f"Polling Azure fallito ({polled.status_code}): "
                    f"{polled.text[:800]}"
                )
            payload = polled.json()
            status = str(payload.get("status") or "").lower()
            if status == "succeeded":
                return self._extract_content(payload)
            if status in {"failed", "canceled"}:
                error = payload.get("error") or {}
                raise AzureDocumentIntelligenceError(
                    f"Analisi Azure {status}: {error}"
                )
            time.sleep(max(0.25, self.config.poll_interval_seconds))

        raise AzureDocumentIntelligenceError(
            "Timeout durante l'analisi Azure Document Intelligence."
        )

    @staticmethod
    def _extract_content(payload: dict) -> str:
        result = payload.get("analyzeResult") or payload.get("result") or payload
        content = str((result or {}).get("content") or "").strip()
        if not content:
            raise AzureDocumentIntelligenceError(
                "Azure Document Intelligence non ha restituito contenuto testuale."
            )
        return content


def azure_document_intelligence_configured() -> bool:
    return AzureDocumentIntelligenceConfig.from_env() is not None
