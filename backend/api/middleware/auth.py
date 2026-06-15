"""Supabase JWT validation for FastAPI."""

from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config.settings import get_settings

_bearer = HTTPBearer(auto_error=False)


def _decode_token(token: str) -> dict:
    settings = get_settings()
    secret = settings.supabase_jwt_secret
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SUPABASE_JWT_SECRET not configured",
        )
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e


def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[UUID]:
    if not credentials:
        return None
    payload = _decode_token(credentials.credentials)
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return UUID(sub)
    except ValueError:
        return None


def get_current_user_id(
    user_id: Optional[UUID] = Depends(get_optional_user_id),
) -> UUID:
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user_id
