#!/usr/bin/env python3
"""Try Supabase connection modes; run from repo root after filling .env."""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend.config.database_url import CONNECTION_MODES, build_database_url
from backend.config.settings import get_settings

import psycopg


def try_url(label: str, url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=12) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        print(f"  OK   {label}")
        return True
    except Exception as exc:
        print(f"  FAIL {label}: {str(exc)[:90]}")
        return False


def main() -> None:
    settings = get_settings()
    ref = settings.supabase_project_ref
    pwd = settings.supabase_db_password
    region = settings.supabase_region

    print("TariffIQ DB connection probe\n")
    if settings.database_url.strip():
        try_url("DATABASE_URL (explicit)", settings.resolved_database_url)
        return

    if not ref or not pwd:
        print("Set SUPABASE_DB_PASSWORD (and SUPABASE_URL) in .env")
        sys.exit(1)

    print(f"Project: {ref}  Region: {region}\n")

    for mode in CONNECTION_MODES:
        if mode == "direct":
            label = f"{mode} → db.{ref}.supabase.co"
            url = build_database_url(
                project_ref=ref, password=pwd, region=region, mode=mode
            )
            if try_url(label, url):
                print(f"\nUse in .env:\n  DATABASE_CONNECTION={mode}")
                sys.exit(0)
            continue
        for idx in (0, 1):
            label = f"{mode} @ aws-{idx}-{region}"
            url = build_database_url(
                project_ref=ref,
                password=pwd,
                region=region,
                mode=mode,
                pooler_host_index=idx,
            )
            if try_url(label, url):
                print(f"\nUse in .env:\n  DATABASE_CONNECTION={mode}")
                if mode != "direct":
                    print(f"  # pooler index aws-{idx} worked")
                sys.exit(0)

    print("\nNo mode worked. Copy URI from Supabase Dashboard → Connect → Session pooler")
    print("and set DATABASE_URL=... explicitly in .env")
    sys.exit(1)


if __name__ == "__main__":
    main()
