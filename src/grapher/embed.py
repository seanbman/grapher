"""Embedding providers: fastembed (default) and OpenAI-compatible API."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_OPENAI_MODEL = "text-embedding-3-small"


class EmbedError(Exception):
    pass


class Embedder(Protocol):
    provider: str
    model: str
    dims: int | None

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _normalize(vec: list[float]) -> list[float]:
    norm = sum(x * x for x in vec) ** 0.5
    if norm == 0:
        return vec
    return [x / norm for x in vec]


class FastEmbedEmbedder:
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as e:
            raise EmbedError(
                "semantic search requires the embed extra: "
                'pip install -e ".[embed]"'
            ) from e
        self.provider = "fastembed"
        self.model = model
        self._model = TextEmbedding(model_name=model)
        self.dims: int | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        raw = list(self._model.embed(texts))
        out: list[list[float]] = []
        for v in raw:
            vec = [float(x) for x in v]
            if self.dims is None:
                self.dims = len(vec)
            out.append(_normalize(vec))
        return out


class OpenAIEmbedder:
    def __init__(
        self,
        model: str = DEFAULT_OPENAI_MODEL,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.provider = "openai"
        self.model = model
        self.dims: int | None = None
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise EmbedError(
                "OPENAI_API_KEY is required for provider=openai"
            )
        base = (
            base_url
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        self._url = f"{base}/embeddings"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        body = json.dumps({"model": self.model, "input": texts}).encode("utf-8")
        req = urllib.request.Request(
            self._url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise EmbedError(f"openai embeddings failed: {e.code} {detail}") from e
        except urllib.error.URLError as e:
            raise EmbedError(f"openai embeddings request failed: {e}") from e

        data = payload.get("data") or []
        data = sorted(data, key=lambda d: d.get("index", 0))
        out: list[list[float]] = []
        for item in data:
            vec = [float(x) for x in item["embedding"]]
            if self.dims is None:
                self.dims = len(vec)
            out.append(_normalize(vec))
        return out


def get_embedder(
    provider: str | None = None,
    model: str | None = None,
) -> Embedder:
    prov = (
        provider
        or os.environ.get("GRAPHER_EMBED_PROVIDER")
        or "fastembed"
    ).lower()
    if prov == "fastembed":
        return FastEmbedEmbedder(model or DEFAULT_MODEL)
    if prov in {"openai", "openai-compatible"}:
        return OpenAIEmbedder(model or DEFAULT_OPENAI_MODEL)
    raise EmbedError(f"unknown embed provider: {prov}")
