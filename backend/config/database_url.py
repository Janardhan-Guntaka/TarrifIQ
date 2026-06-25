"""Build Supabase Postgres connection URLs for local vs cloud."""

from __future__ import annotations

from urllib.parse import quote_plus

# direct: IPv6 db host — works from AWS/Vercel CI; often times out on Windows home networks
# pooler-session: port 5432 — best for long ingest jobs locally
# pooler-transaction: port 6543 — good for API request handlers / cloud
CONNECTION_MODES = ("direct", "pooler-session", "pooler-transaction")


def project_ref_from_supabase_url(supabase_url: str) -> str:
    """Extract project ref from https://<ref>.supabase.co."""
    url = (supabase_url or "").strip().rstrip("/")
    if not url:
        return ""
    host = url.replace("https://", "").replace("http://", "").split("/")[0]
    return host.split(".")[0] if host else ""


def build_database_url(
    *,
    project_ref: str,
    password: str,
    region: str = "us-east-1",
    mode: str = "pooler-session",
    pooler_host_index: int = 0,
) -> str:
    """
    Build a Supabase Postgres URI.

    Copy the exact URI from Supabase Dashboard → Connect if auto-built URLs fail.
    """
    ref = project_ref.strip()
    pwd = quote_plus(password.strip())
    if not ref or not password.strip():
        raise ValueError("project_ref and password are required to build DATABASE_URL")

    mode = mode.strip().lower()
    if mode == "direct":
        return f"postgresql://postgres:{pwd}@db.{ref}.supabase.co:5432/postgres?sslmode=require"

    pooler = f"aws-{pooler_host_index}-{region}.pooler.supabase.com"
    user = f"postgres.{ref}"
    port = "5432" if mode == "pooler-session" else "6543"
    if mode not in ("pooler-session", "pooler-transaction"):
        raise ValueError(f"Unknown DATABASE_CONNECTION mode: {mode}")
    return f"postgresql://{user}:{pwd}@{pooler}:{port}/postgres?sslmode=require"
