"""OpenAI embedding service (production path — no local models)."""

from typing import Sequence

from openai import OpenAI

from backend.config.settings import get_settings


class OpenAIEmbeddingService:
    def __init__(self) -> None:
        settings = get_settings()
        settings.require_openai()
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_embed_model
        self._dimensions = settings.embedding_dimensions

    @property
    def model_name(self) -> str:
        return self._model

    def embed_query(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: Sequence[str], batch_size: int = 50) -> list[list[float]]:
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        batch = list(texts)

        for i in range(0, len(batch), batch_size):
            chunk = batch[i : i + batch_size]
            response = self._client.embeddings.create(
                model=self._model,
                input=chunk,
                dimensions=self._dimensions,
            )
            ordered = sorted(response.data, key=lambda d: d.index)
            all_vectors.extend([d.embedding for d in ordered])

        return all_vectors
