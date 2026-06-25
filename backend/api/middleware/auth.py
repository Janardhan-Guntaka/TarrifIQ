"""Supabase JWT validation for FastAPI (HS256 legacy + ES256 JWKS)."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from backend.config.settings import get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthUser:
    id: UUID
    email: str


@lru_cache
def _jwks_client(supabase_url: str) -> PyJWKClient:
    url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(url, cache_keys=True)


def _decode_token(token: str) -> dict:
    settings = get_settings()

    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e

    alg = header.get("alg", "")
    issuer = (
        f"{settings.supabase_url.rstrip('/')}/auth/v1" if settings.supabase_url else None
    )
    decode_kw: dict = {"algorithms": [alg], "audience": "authenticated"}
    if issuer:
        decode_kw["issuer"] = issuer

    try:
        if alg == "HS256":
            secret = settings.supabase_jwt_secret
            if not secret:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SUPABASE_JWT_SECRET not configured for HS256 tokens",
                )
            return jwt.decode(token, secret, **decode_kw)

        if alg in ("ES256", "RS256"):
            if not settings.supabase_url:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="SUPABASE_URL not configured for JWKS verification",
                )
            client = _jwks_client(settings.supabase_url)
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(token, signing_key.key, **decode_kw)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Unsupported JWT algorithm: {alg}",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[AuthUser]:
    if not credentials:
        return None
    payload = _decode_token(credentials.credentials)
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return AuthUser(id=UUID(sub), email=payload.get("email") or "")
    except ValueError:
        return None


def get_optional_user_id(
    user: Optional[AuthUser] = Depends(get_optional_user),
) -> Optional[UUID]:
    return user.id if user else None


def get_current_user(
    user: Optional[AuthUser] = Depends(get_optional_user),
) -> AuthUser:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def get_current_user_id(user: AuthUser = Depends(get_current_user)) -> UUID:
    return user.id
