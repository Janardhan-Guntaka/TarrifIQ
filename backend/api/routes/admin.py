"""Admin endpoints for release management (local / pre-GHA)."""

from fastapi import APIRouter, HTTPException

from backend.core.deps import get_deps

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/releases")
def list_releases(limit: int = 50):
    return get_deps().releases.list_all(limit=limit)


@router.get("/releases/active")
def active_release():
    active = get_deps().releases.get_active()
    if not active:
        raise HTTPException(status_code=404, detail="No active release")
    return active
