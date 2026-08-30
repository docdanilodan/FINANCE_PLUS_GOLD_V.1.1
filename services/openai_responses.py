from __future__ import annotations

import json
import os
from typing import Any, Dict

import requests


class OpenAIResponsesClient:
    """Small server-side wrapper around the OpenAI Responses API.

    The API key is read only from the environment/secret store and is never
    persisted in Airtable or GitHub.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY non configurata")

    @staticmethod
    def _output_text(payload: Dict[str, Any]) -> str:
        parts: list[str] = []
        for item in payload.get("output", []) or []:
            for content in item.get("content", []) or []:
                text = content.get("text")
                if text:
                    parts.append(str(text))
        return "\n".join(parts).strip()

    def create(self, *, instructions: str, input_text: str) -> str:
        response = requests.post(
            f"{self.base_url}/responses",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "instructions": instructions,
                "input": input_text,
            },
            timeout=90,
        )
        response.raise_for_status()
        return self._output_text(response.json())

    def operational_recommendation(self, entity: str, fields: Dict[str, Any]) -> str:
        safe_fields = {
            key: value
            for key, value in fields.items()
            if key not in {"Codice Fiscale", "Partita IVA", "PEC", "Email"}
        }
        return self.create(
            instructions=(
                "Sei il motore operativo di FinancePlus 360 AI. Analizza esclusivamente i dati "
                "forniti. Non inventare importi, rating, KPI o documenti mancanti. Restituisci una "
                "raccomandazione operativa concisa in italiano, indicando eventuali dati insufficienti."
            ),
            input_text=f"Entità: {entity}\nDati strutturati:\n{json.dumps(safe_fields, ensure_ascii=False, default=str)}",
        )
