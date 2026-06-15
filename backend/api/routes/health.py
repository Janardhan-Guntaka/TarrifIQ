from fastapi import APIRouter

from backend.config.settings import get_settings
from backend.core.deps import get_deps
from backend.services.supabase_client import SupabaseClientService

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    settings = get_settings()
    deps = get_deps()
    active = deps.releases.get_active()
    return {
        "status": "ok",
        "service": "tariffiq",
        "environment": settings.environment,
        "active_release": active["version"] if active else None,
        "policy_version": deps.policy.get_composite_version(),
        "embed_model": deps.embedding_service.model_name,
        "llm_model": deps.llm_service.model_name,
    }


@router.get("/health/supabase")
def health_supabase():
    return SupabaseClientService().health_check()
