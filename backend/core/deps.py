"""Dependency injection container for repositories and services."""

from functools import lru_cache

from backend.repositories.hts_nodes import HtsNodeRepository
from backend.repositories.pgvector import PgVectorRepository
from backend.repositories.policy import PolicyRepository
from backend.repositories.queries import QueryRepository
from backend.repositories.releases import ReleaseRepository
from backend.services.embedding_service import OpenAIEmbeddingService
from backend.services.llm_service import OpenAILLMService


class AppDependencies:
    """Wire all repositories and services for graph nodes and API routes."""

    def __init__(self) -> None:
        self.embedding_service = OpenAIEmbeddingService()
        self.llm_service = OpenAILLMService()
        self.hts_nodes = HtsNodeRepository()
        self.vector = PgVectorRepository(self.embedding_service)
        self.policy = PolicyRepository()
        self.queries = QueryRepository()
        self.releases = ReleaseRepository()


@lru_cache
def get_deps() -> AppDependencies:
    return AppDependencies()


def reset_deps() -> None:
    """Clear cached deps (useful in tests)."""
    get_deps.cache_clear()
