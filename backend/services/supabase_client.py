"""Supabase REST client helpers (auth verification)."""

from typing import Any

import httpx

from backend.config.settings import get_settings


class SupabaseClientService:
    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def url(self) -> str:
        return self._settings.supabase_url.rstrip("/")

    @property
    def anon_key(self) -> str:
        return self._settings.supabase_anon_key

    @property
    def service_role_key(self) -> str:
        return self._settings.supabase_service_role_key

    def headers(self, *, service: bool = False) -> dict[str, str]:
        key = self.service_role_key if service else self.anon_key
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def health_check(self) -> dict[str, Any]:
        """Lightweight check that Supabase URL is reachable."""
        if not self.url:
            return {"ok": False, "error": "SUPABASE_URL not set"}
        try:
            with httpx.Client(timeout=5.0) as client:
                r = client.get(f"{self.url}/rest/v1/", headers=self.headers())
            return {"ok": r.status_code < 500, "status_code": r.status_code}
        except Exception as e:
            return {"ok": False, "error": str(e)}
