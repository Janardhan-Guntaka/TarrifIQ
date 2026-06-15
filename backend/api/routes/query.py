from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.api.middleware.auth import get_current_user_id, get_optional_user_id
from backend.api.schemas.query import ClassifyRequest, ClassifyResponse, QueryListItem
from backend.core.deps import get_deps
from backend.services.query_service import QueryService

router = APIRouter(prefix="/v1", tags=["query"])


@router.post("/classify", response_model=ClassifyResponse)
def classify(
    body: ClassifyRequest,
    user_id=Depends(get_optional_user_id),
):
    """
    Classify product and estimate duties.
    Auth optional in development — set Authorization: Bearer <jwt> when configured.
    """
    try:
        result = QueryService().classify(
            raw_query=body.query,
            country=body.country,
            customs_value=body.customs_value,
            user_id=user_id,
        )
        return ClassifyResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/queries", response_model=list[QueryListItem])
def list_queries(
    limit: int = 50,
    user_id: UUID = Depends(get_current_user_id),
):
    rows = get_deps().queries.list_for_user(user_id, limit=limit)
    return [QueryListItem(**r) for r in rows]


@router.get("/queries/{query_id}", response_model=ClassifyResponse)
def get_query(
    query_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
):
    row = get_deps().queries.get_by_id(query_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Query not found")
    payload = row.get("response_json") or {}
    payload["query_id"] = str(row["id"])
    return ClassifyResponse(**payload)
