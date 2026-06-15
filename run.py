"""
run.py — TariffIQ V2 entry point.

Usage:
    python run.py api
    python run.py classify "gaming laptop from China"
    python run.py ingest --version 2026HTSRev6 --skip-parse --activate
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_api() -> None:
    import uvicorn

    print("\n  TariffIQ V2 — FastAPI backend")
    print("  Docs:   http://localhost:8000/docs")
    print("  Health: http://localhost:8000/health\n")
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(ROOT)],
    )


def run_classify(query: str) -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from backend.services.query_service import QueryService

    print(f"Query: {query}")
    print("─" * 60)
    result = QueryService().classify(raw_query=query)
    import json

    print(json.dumps(result, indent=2, default=str))


def run_ingest(argv: list[str]) -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    from backend.scripts import ingest_local

    sys.argv = ["ingest_local"] + argv
    ingest_local.main()


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python run.py classify "your trade query"')
        print("  python run.py api")
        print("  python run.py ingest --version VERSION [--file PATH] [--skip-parse] [--activate]")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "api":
        run_api()
    elif command == "classify":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else \
                "gaming laptop imported from China what is the import duty"
        run_classify(query)
    elif command == "ingest":
        run_ingest(sys.argv[2:])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
