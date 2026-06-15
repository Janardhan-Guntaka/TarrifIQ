#!/usr/bin/env python3
"""
Local HTS ingestion: parse → chunk → embed → Supabase.

Does NOT run automatically. Execute manually after migrations:

  python -m backend.scripts.ingest_local --version 2026HTSRev6 --file data/raw/hts/hts_2026HTSRev6.json
  python -m backend.scripts.ingest_local --version 2026HTSRev6 --activate
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest HTS release into Supabase")
    ap.add_argument("--version", required=True, help="Release version e.g. 2026HTSRev6")
    ap.add_argument("--file", help="Path to raw HTS JSON (runs parse if set)")
    ap.add_argument("--skip-parse", action="store_true", help="Use existing processed JSONL")
    ap.add_argument("--activate", action="store_true", help="Set this release active after ingest")
    ap.add_argument("--no-embed", action="store_true", help="Load nodes only, skip embeddings")
    args = ap.parse_args()

    from backend.scripts._ingest_runner import run_ingestion

    run_ingestion(
        version=args.version,
        raw_file=pathlib.Path(args.file) if args.file else None,
        skip_parse=args.skip_parse,
        activate=args.activate,
        embed=not args.no_embed,
    )


if __name__ == "__main__":
    main()
