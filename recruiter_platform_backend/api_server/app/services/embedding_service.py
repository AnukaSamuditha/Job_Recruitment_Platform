"""Local Ollama embedding calls (async via HTTP)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Batch and single-text embeddings against Ollama `/api/embed`."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._base = self._settings.ollama_base_url.rstrip("/")
        self._model = self._settings.ollama_embed_model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input string (same order)."""
        if not texts:
            return []
        payload: dict[str, Any] = {"model": self._model, "input": texts}
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self._base}/api/embed", json=payload)
            resp.raise_for_status()
            data = resp.json()
        if "embeddings" in data:
            return data["embeddings"]
        if "embedding" in data:
            return [data["embedding"]]
        raise RuntimeError(f"Unexpected Ollama embed response keys: {data.keys()}")

    async def embed_one(self, text: str) -> list[float]:
        vecs = await self.embed_texts([text])
        return vecs[0]
