"""
run.py
------
Project entry point. Run all scripts through this file to ensure
the project root is on sys.path so imports like 'from graph.state import...'
work correctly.

Usage:
    # Test the pipeline
    python run.py pipeline "gaming laptop from China"

    # Run the API
    python run.py api

    # Run the UI
    python run.py ui

    # Run any script directly
    python run.py script graph/pipeline.py "your query here"
"""

import sys
import os
import pathlib

# ── fix sys.path ──────────────────────────────────────────────────────────────
# Add the project root (folder containing graph/, stores/, etc.) to sys.path
# This makes 'from graph.state import ...' work from any subfolder
ROOT = pathlib.Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── entry points ──────────────────────────────────────────────────────────────

def run_pipeline(query: str) -> None:
    from graph.pipeline import run
    import json

    print(f"Query: {query}")
    print("─" * 60)

    result = run(query)

    print(f"\n[ANALYZER]")
    print(f"  Product    : {result['product_description']}")
    print(f"  HTS term   : {result['hts_search_term']}")
    print(f"  Origin     : {result['origin_country']}")
    print(f"  Scenario   : {result['trade_scenario']}")

    print(f"\n[CLASSIFIER]")
    print(f"  HTS Code   : {result['selected_hts_code']}")
    print(f"  Heading    : {result['selected_heading']}")
    print(f"  Chapter    : {result['selected_chapter']}")
    print(f"  Confidence : {result['confidence_score']:.0%}")
    print(f"  Escalate   : {result['escalate']}")
    if result.get('escalate_reason'):
        print(f"  Reason     : {result['escalate_reason']}")

    print(f"\n[TARIFF]")
    print(f"  General    : {result['general_rate']}")
    print(f"  Applicable : {result['applicable_rate']} ({result['rate_basis']})")
    print(f"  Sec 301    : {result['section_301']}  {result['section_301_rate']}")
    print(f"  Total est. : {result['total_rate_estimate']}")

    print(f"\n[ANSWER]")
    print(result["final_answer"])

    print(f"\n[CITATIONS]")
    for c in result.get("citations", []):
        print(f"  • {c}")

    print(f"\n[DISCLAIMER]")
    print(result["disclaimer"])


def run_api() -> None:
    import uvicorn
    print("\n  Vanguard AI — FastAPI backend")
    print("  Docs: http://localhost:8000/docs")
    print("  Health: http://localhost:8000/health\n")
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[str(ROOT)],
    )


def run_ui() -> None:
    import subprocess
    print("\n  Vanguard AI — Streamlit UI")
    print("  Opening: http://localhost:8501\n")
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "ui/app.py",
         "--server.headless", "false",
         "--browser.gatherUsageStats", "false"],
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python run.py pipeline \"your trade query\"")
        print("  python run.py api")
        print("  python run.py ui")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "pipeline":
        query = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else \
                "gaming laptop imported from China what is the import duty"
        run_pipeline(query)

    elif command == "api":
        run_api()

    elif command == "ui":
        run_ui()

    else:
        print(f"Unknown command: {command}")
        print("Commands: pipeline, api, ui")
        sys.exit(1)


if __name__ == "__main__":
    main()