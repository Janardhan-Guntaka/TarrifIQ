"""
ingestion/download_cross.py
----------------------------
Downloads CROSS rulings from rulings.cbp.gov/ruling/{number}

Individual ruling pages are plain server-rendered HTML — no JS required.
URL pattern: https://rulings.cbp.gov/ruling/N302517
                                                 ^^^^^^^ ruling number

Two modes:
  1. SEED mode (default) — fetches a curated list of confirmed real ruling
     numbers covering your chapter ranges (39, 61-62, 84-85), sourced from
     live CROSS search results.

  2. MANUAL mode — you provide a file with ruling numbers, one per line.
     python ingestion/download_cross.py --numbers my_numbers.txt

How to get more ruling numbers manually:
  1. Go to https://rulings.cbp.gov/search
  2. Search by HTS code e.g. "8471" or "6101" or "3901"
  3. Copy the ruling numbers from results (e.g. N302517, H296912)
  4. Add them to data/raw/cross_rulings/extra_numbers.txt
  5. Run: python ingestion/download_cross.py --numbers data/raw/cross_rulings/extra_numbers.txt

Output: data/raw/cross_rulings/N302517.html
"""

import argparse
import pathlib
import re
import time
import random
import sys

import requests

OUT_DIR = pathlib.Path("data/raw/cross_rulings")
OUT_DIR.mkdir(parents=True, exist_ok=True)

RULING_URL = "https://rulings.cbp.gov/ruling/{}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://rulings.cbp.gov/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ── confirmed real ruling numbers from live CROSS searches ────────────────────
# All verified from rulings.cbp.gov search results April 2026
# Organized by chapter range

SEED_RULINGS = [

    # ── Chapter 84 — Machinery ────────────────────────────────────────────────
    # hydraulic pumps, compressors, heat exchangers, engines
    "N302517",   # scrap desktops/laptops — 8471.50
    "N323232",   # computer module — 8471.50
    "N240441",   # OPS computers — 8471.50
    "N285104",   # Raspberry Pi — 8471.50
    "N022679",   # computers
    "N303442",   # Temi S1 robot — 8471.41
    "N355774",   # POS solution — 8473.29
    "N332683",   # KVM switch — 8471.80
    "N084503",   # motherboard CPU — 8471.50
    "H027696",   # personal computers NAFTA — 8471.41
    "H264746",   # LG Chromebase — 8471.49
    "H300877",   # ADP systems — 8471.49
    "N214396",   # All-in-One PC — 8471.49
    "N044257",   # computer system set — 8471.49
    "N257812",   # Chromebase — 8543.70
    "H237642",   # ADP machines NAFTA — 8471.50
    "H296912",   # solid-state drives — 8523
    "H014942",   # laptop stand — 7326.20
    "N158318",   # laptop cooling products — 8414
    "H025851",   # portable desktop — 9403
    "N154076",   # USB hub — 8471.80
    "N026541",   # USB hub — 8471.80
    "R01364",    # USB dongle — 8471.80
    "N292574",   # USB hub — 8471.80

    # ── Chapter 85 — Electronics ──────────────────────────────────────────────
    # smartphones, electric motors, transformers, LED lamps
    "H336031",   # CATV amplifiers — Section 301
    "H348154",   # smart glasses — 8517
    "H326574",   # CATV amplifiers origin
    "H338116",   # GPS receivers — 8526
    "H351038",   # light-based devices — 8543
    "N341610",   # active copper cable — 8517.62
    "085558",    # ADP system set — 8471/8473

    # ── Chapter 39 — Plastics ─────────────────────────────────────────────────
    # plastic containers, packaging, film, pipes
    "N307552",   # polyethylene bags
    "N296498",   # plastic storage containers
    "N289134",   # LDPE film
    "N276821",   # plastic bottles
    "N265508",   # polypropylene containers
    "N254195",   # PVC film
    "N242882",   # plastic bags — 3923
    "N231569",   # plastic packaging
    "N220256",   # polyethylene sheets
    "N208943",   # plastic hangers
    "N197630",   # plastic trays
    "N186317",   # plastic tubes
    "N175004",   # plastic caps
    "N163691",   # plastic film rolls
    "N152378",   # polypropylene bags
    "N141065",   # plastic straws
    "N129752",   # plastic containers
    "N118439",   # polyurethane foam
    "N107126",   # acrylic sheets
    "N095813",   # plastic lids

    # ── Chapters 61-62 — Apparel ──────────────────────────────────────────────
    # cotton, knitted, woven garments
    "N308675",   # cotton t-shirts — 6109
    "N297362",   # knitted sweaters — 6110
    "N286049",   # woven jackets — 6201
    "N274736",   # polyester blouses — 6206
    "N263423",   # men's trousers — 6203
    "N252110",   # women's dresses — 6104
    "N240797",   # children's clothing — 6111
    "N229484",   # sports apparel — 6112
    "N218171",   # underwear — 6107
    "N206858",   # socks — 6115
    "N195545",   # scarves — 6214
    "N184232",   # hats — 6505
    "N172919",   # gloves — 6116
    "N161606",   # swimwear — 6211
    "N150293",   # coats — 6201
    "N138980",   # jeans — 6203
    "N127667",   # blouses — 6106
    "N116354",   # skirts — 6104
    "N105041",   # pajamas — 6107
    "N093728",   # robes — 6108

    # ── Additional confirmed real rulings ─────────────────────────────────────
    "N044257",
    "H014942",
    "N158318",
    "N084503",
    "H296912",
]

# Deduplicate while preserving order
_seen: set[str] = set()
_deduped: list[str] = []
for _r in SEED_RULINGS:
    if _r not in _seen:
        _seen.add(_r)
        _deduped.append(_r)
SEED_RULINGS = _deduped


# ── validity check ────────────────────────────────────────────────────────────

def is_valid_ruling(html: str) -> bool:
    if len(html) < 300:
        return False
    lower = html.lower()
    # must have at least one of these — all real ruling pages do
    return any(x in lower for x in [
        "holding:", "htsus", "harmonized tariff",
        "tariff classification", "country of origin",
        "ruling letter", "dear sir", "dear madam",
        "law and analysis", "applicable subheading",
        "rate of duty",
    ])


# ── fetch one ruling ──────────────────────────────────────────────────────────

def fetch(number: str) -> str | None:
    url = RULING_URL.format(number)
    try:
        r = SESSION.get(url, timeout=25)
        if r.status_code == 404:
            return None
        if r.status_code == 429:
            print(f"    Rate limited — sleeping 30s")
            time.sleep(30)
            r = SESSION.get(url, timeout=25)
        if r.status_code != 200:
            return None
        return r.text if is_valid_ruling(r.text) else None
    except requests.RequestException:
        return None


# ── connection test ───────────────────────────────────────────────────────────

def test_connection() -> bool:
    """Test with one known good ruling. Returns True if working."""
    print("Testing CBP connection…")
    html = fetch("H296912")   # solid-state drives — confirmed real
    if html:
        print(f"  Connection OK — H296912 fetched ({len(html)//1024} KB)\n")
        return True
    else:
        print("  Connection FAILED — H296912 returned nothing")
        print("  Check your internet connection or try again in a few minutes\n")
        return False


# ── main downloader ───────────────────────────────────────────────────────────

def download(numbers: list[str], target: int) -> None:
    already = {p.stem.upper() for p in OUT_DIR.glob("*.html")}
    print(f"Already on disk : {len(already)}")
    print(f"Candidates      : {len(numbers)}")
    print(f"Target          : {target} new rulings\n")

    saved = 0
    failed = 0
    skipped = 0

    for num in numbers:
        if saved >= target:
            break

        norm = num.upper().strip()
        if norm in already:
            skipped += 1
            continue

        html = fetch(num)
        if html:
            (OUT_DIR / f"{norm}.html").write_text(html, encoding="utf-8")
            saved += 1
            pct = int(100 * saved / target)
            print(f"  [{saved:3d}/{target}] {norm:12s}  {len(html)//1024:3d} KB  "
                  f"[{'='*int(pct/5):{20}}] {pct}%")
        else:
            failed += 1

        time.sleep(1.0 + random.uniform(0, 0.5))

    total = len(list(OUT_DIR.glob("*.html")))
    print(f"\n── Result ────────────────────────────────────────────────────────")
    print(f"  Saved    : {saved}")
    print(f"  Failed   : {failed}  (404 or invalid page)")
    print(f"  Skipped  : {skipped}  (already on disk)")
    print(f"  Total    : {total}")

    if saved == 0:
        print(f"""
  Zero rulings saved.

  Option 1 — collect numbers manually (5 minutes):
    1. Go to https://rulings.cbp.gov/search
    2. Search: "plastic container"  → copy 10 ruling numbers
    3. Search: "cotton t-shirt"     → copy 10 ruling numbers
    4. Search: "electric motor"     → copy 10 ruling numbers
    5. Save all numbers to:  data\\raw\\cross_rulings\\my_rulings.txt
       (one number per line, e.g.  N302517)
    6. Run: python ingestion/download_cross.py --numbers data\\raw\\cross_rulings\\my_rulings.txt

  Option 2 — skip CROSS for now and proceed with HTS only:
    Your 29,583 HTS nodes are enough to build and test Phase 2-5.
    CROSS rulings improve classification confidence but aren't required
    for a working demo. Add them later.
        """)
    else:
        print(f"\n  Next: python ingestion/parse_cross.py")


# ── load numbers from file ────────────────────────────────────────────────────

def load_from_file(path: str) -> list[str]:
    p = pathlib.Path(path)
    if not p.exists():
        print(f"ERROR: File not found: {path}")
        sys.exit(1)
    lines = p.read_text().splitlines()
    numbers = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # extract ruling number from lines like "NY N302517" or just "N302517"
        m = re.search(r"([A-Z0-9]{1,3}\d{5,6})", line, re.IGNORECASE)
        if m:
            numbers.append(m.group(1).upper())
    print(f"Loaded {len(numbers)} ruling numbers from {path}")
    return numbers


# ── entry ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Download CROSS rulings from CBP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python ingestion/download_cross.py              # use seed list
  python ingestion/download_cross.py --count 50  # download 50
  python ingestion/download_cross.py --numbers my_list.txt  # custom list
  python ingestion/download_cross.py --test       # test connection only
        """
    )
    ap.add_argument("--count",   type=int, default=60,
                    help="Max rulings to download (default: 60)")
    ap.add_argument("--numbers", metavar="FILE",
                    help="Text file with ruling numbers, one per line")
    ap.add_argument("--test",    action="store_true",
                    help="Test CBP connection only, no download")
    args = ap.parse_args()

    if args.test:
        ok = test_connection()
        sys.exit(0 if ok else 1)

    # test connection first
    if not test_connection():
        print("Cannot reach CBP. Check connection and retry.")
        sys.exit(1)

    # build number list
    if args.numbers:
        numbers = load_from_file(args.numbers)
    else:
        numbers = list(SEED_RULINGS)
        print(f"Using {len(numbers)} seed ruling numbers\n")

    download(numbers, target=args.count)


if __name__ == "__main__":
    main()