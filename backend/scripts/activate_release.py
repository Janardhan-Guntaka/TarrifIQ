#!/usr/bin/env python3
"""Activate an HTS release by version string."""

import argparse
import pathlib
import sys

from dotenv import load_dotenv

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    args = ap.parse_args()

    from backend.core.deps import get_deps

    deps = get_deps()
    rel = deps.releases.get_by_version(args.version)
    if not rel:
        raise SystemExit(f"Release not found: {args.version}")

    deps.releases.activate(rel["id"])
    print(f"Activated: {args.version}")


if __name__ == "__main__":
    main()
