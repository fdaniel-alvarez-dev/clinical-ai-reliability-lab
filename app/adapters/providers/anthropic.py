from __future__ import annotations

import os
from typing import Any

import httpx

from app.adapters.providers.base import LLMProvider
from app.models.patient import NormalizedPatient
from app.workflows.biomarker_graph.models import BiomarkerConcern


class AnthropicProvider(LLMProvider):
    """
    Optional provider adapter.

    This repo defaults to the mock provider for determinism and to avoid paid API access.
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        self._model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    async def generate_chr_draft(
        self,
        *,
        normalized: NormalizedPatient,
        workflow: str,
        concerns: list[BiomarkerConcern],
    ) -> dict[str, Any]:
        # Intentionally minimal: production use would require stricter prompting + retries + timeouts.
        # We still enforce determinism *after* generation via deterministic validators.
        prompt = {
            "task": "Generate a Comprehensive Health Report draft as strict JSON matching chr_v1.",
            "workflow": workflow,
            "constraints": [
                "Synthetic data only.",
                "No diagnoses, prescribing, or medical advice.",
                "Every finding and recommendation must include evidence refs pointing to input items.",
            ],
            "biomarker_graph_concerns": [c.model_dump(mode="json") for c in concerns],
            "input": normalized.model_dump(mode="json"),
        }
        assert self._api_key is not None
        headers: dict[str, str] = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 1200,
            "temperature": 0,
            "messages": [{"role": "user", "content": str(prompt)}],
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages", headers=headers, json=body
            )
            resp.raise_for_status()
        data: dict[str, Any] = resp.json()

        # Provider response parsing deliberately conservative: downstream schema validation will fail if wrong.
        text = data.get("content", [{}])[0].get("text", "")
        # Expect the model to return JSON string. If not, validator will reject via schema failures.
        import json

        parsed: Any = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Anthropic response did not parse to a JSON object.")
        return parsed
