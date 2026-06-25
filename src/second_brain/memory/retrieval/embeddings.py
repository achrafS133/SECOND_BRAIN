from __future__ import annotations

import logging
from functools import lru_cache

import numpy as np

from second_brain.config import Settings, get_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Local sentence-transformer embeddings with hash fallback."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._settings.embedding_model)
                logger.info("Loaded embedding model: %s", self._settings.embedding_model)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Embedding model unavailable, using hash fallback: %s", exc)
                self._model = "fallback"
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load_model()
        if model == "fallback":
            return [self._hash_embed(text) for text in texts]
        vectors = model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, query: str) -> list[float]:
        return self.embed([query])[0]

    def _hash_embed(self, text: str) -> list[float]:
        dim = self._settings.embedding_dimension
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        vec = rng.normal(size=dim)
        vec = vec / np.linalg.norm(vec)
        return vec.tolist()


@lru_cache
def get_embedding_service() -> EmbeddingService:
    return EmbeddingService()
