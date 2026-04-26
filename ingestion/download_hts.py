"""
ingestion/download_hts.py
--------------------------
HTS downloader + manifest manager.

USITC blocks automated downloads with 403 on their CDN paths.
This script handles three modes:

  MODE 1 — Register a file you already downloaded manually (most common)
    python ingestion/download_hts.py --register data/raw/hts/hts_2026HTSRev5.json

  MODE 2 — Attempt auto-download (works if USITC unblocks, otherwise gives
            clear manual instructions)
    python ingestion/download_hts.py

  MODE 3 — Check what's latest without downloading
    python ingestion/download_hts.py --check

  MODE 4 — Force re-register an existing file with a specific release name
    python ingestion/download_hts.py --register data/raw/hts/myfile.json --release 2026HTSRev5

How to get the JSON manually (takes 30 seconds):
  1. Open https://hts.usitc.gov/download in your browser
  2. Find the latest revision row (e.g. "2026 HTS Revision 5")
  3. Click the JSON button — browser downloads it directly
  4. Move/rename the file to:  data/raw/hts/hts_2026HTSRev5.json
  5. Run:  python ingestion/download_hts.py --register data/raw/hts/hts_2026HTSRev5.json
"""

import argparse
import hashlib
import json
import pathlib
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# ── paths ─────────────────────────────────────────────────────────────────────
RAW_DIR  = pathlib.Path("data/raw/hts")
MANIFEST = pathlib.Path("data/manifest.json")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ── USITC endpoints ────────────────────────────────────────────────────────────
HTS_INFO_PAGE = "https://www.usitc.gov/harmonized_tariff_information"

# CDN patterns to try — USITC blocks these with 403 but worth trying
# They occasionally work depending on the request source
USITC_CDN_PATTERNS = [
    "https://www.usitc.gov/sites/default/files/tata/hts/hts_{year}_revision_{rev}_json.json",
    "https://www.usitc.gov/sites/default/files/tata/hts/hts_{year}_basic_edition_json.json",
    "https://www.usitc.gov/sites/default/files/tata/hts/hts_{year}_rev{rev}_json.json",
    "https://hts.usitc.gov/reststop/api/details/currentView/download/HTS_{year}Rev{rev}/json",
]

# Use a full browser User-Agent — USITC checks this
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/html,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://hts.usitc.gov/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ── manifest ──────────────────────────────────────────────────────────────────

def read_manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text())
        except Exception:
            return {}
    return {}


def write_manifest(updates: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    existing = read_manifest()
    existing.update(updates)
    MANIFEST.write_text(json.dumps(existing, indent=2))
    print(f"  Manifest updated → {MANIFEST}")


# ── file validation ───────────────────────────────────────────────────────────

def validate_hts_json(path: pathlib.Path) -> tuple[bool, str, int]:
    """
    Check that a file is a valid USITC HTS JSON.
    Returns (is_valid, error_message, row_count).
    """
    if not path.exists():
        return False, f"File not found: {path}", 0

    size_mb = path.stat().st_size / 1e6
    if size_mb < 1:
        return False, f"File too small ({size_mb:.1f} MB) — probably not the full HTS", 0

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}", 0

    # unwrap dict wrapper if needed
    if isinstance(data, dict):
        for key in ("HTSData", "htsData", "data", "rows"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break

    if not isinstance(data, list):
        return False, f"Root is {type(data).__name__}, expected list", 0

    if len(data) < 1000:
        return False, f"Only {len(data)} rows — expected 10,000+", 0

    # spot-check first codeable row has expected keys
    sample = next((r for r in data[:50] if isinstance(r, dict) and r.get("htsno")), None)
    if sample is None:
        return False, "No rows with 'htsno' key found in first 50 rows", 0

    missing_keys = [k for k in ("description", "indent", "general") if k not in sample]
    if missing_keys:
        return False, f"Sample row missing expected keys: {missing_keys}", 0

    return True, "", len(data)


def sha256_of_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── release name helpers ──────────────────────────────────────────────────────

def infer_release_from_filename(path: pathlib.Path) -> str:
    """
    Try to extract release name from filename.
    hts_2026HTSRev5.json        → 2026HTSRev5
    hts_2026_revision_5.json    → 2026HTSRev5
    2026_hts_basic_edition.json → 2026HTSBasic
    HTS_2026_Rev5.json          → 2026HTSRev5
    """
    stem = path.stem.lower()

    # pattern: 2026...rev...5
    m = re.search(r"(\d{4}).*rev(?:ision)?[\s_-]*(\d+)", stem)
    if m:
        return f"{m.group(1)}HTSRev{m.group(2)}"

    # pattern: basic edition
    m2 = re.search(r"(\d{4}).*basic", stem)
    if m2:
        return f"{m2.group(1)}HTSBasic"

    # just the year
    m3 = re.search(r"(\d{4})", stem)
    if m3:
        return f"{m3.group(1)}HTSUnknownRev"

    return path.stem


def release_to_cdn_urls(release: str) -> list[str]:
    m = re.match(r"(\d{4})HTS(?:Rev(\d+)|Basic)", release, re.IGNORECASE)
    if not m:
        return []
    year = m.group(1)
    rev  = m.group(2) or "0"
    return [p.format(year=year, rev=int(rev)) for p in USITC_CDN_PATTERNS]


# ── release discovery ─────────────────────────────────────────────────────────

def discover_latest_release() -> tuple[str, str]:
    """
    Scrape USITC info page for latest revision.
    Returns (release_name, date_str) or fallback values.
    """
    print("Checking USITC for latest HTS release …")
    try:
        r = SESSION.get(HTS_INFO_PAGE, timeout=20)
        r.raise_for_status()
        text = BeautifulSoup(r.text, "lxml").get_text(" ")
        m = re.search(
            r"(\d{4})\s+HTS\s+Revision\s+(\d+)\s+was\s+published\s+on\s+(\w+ \d+,\s*\d{4})",
            text
        )
        if m:
            year, rev, date_str = m.group(1), m.group(2), m.group(3)
            release = f"{year}HTSRev{rev}"
            try:
                dt = datetime.strptime(date_str.strip(), "%B %d, %Y")
                formatted = dt.strftime("%m/%d/%Y")
            except ValueError:
                formatted = ""
            print(f"  Latest: {release}  (published {date_str})")
            return release, formatted
    except requests.RequestException as e:
        print(f"  Could not reach USITC ({e})")

    # fallback to what we know from the search results
    fallback = ("2026HTSRev6", "04/23/2026")
    print(f"  Using known fallback: {fallback[0]}")
    return fallback


# ── auto-download attempt ─────────────────────────────────────────────────────

def attempt_download(release: str, out_path: pathlib.Path) -> bool:
    """
    Try downloading the JSON directly. USITC often 403s these,
    but worth attempting in case it works.
    """
    urls = release_to_cdn_urls(release)

    for url in urls:
        print(f"  Trying: {url}")
        try:
            r = SESSION.get(url, stream=True, timeout=120)

            if r.status_code == 403:
                print(f"    403 Forbidden — USITC blocks automated downloads on this path")
                continue
            if r.status_code != 200:
                print(f"    HTTP {r.status_code} — skipping")
                continue

            content_type = r.headers.get("Content-Type", "")
            if "html" in content_type:
                print(f"    Got HTML page, not a JSON file — skipping")
                continue

            # stream to disk
            tmp = out_path.with_suffix(".tmp")
            size = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)
                    size += len(chunk)

            valid, err, rows = validate_hts_json(tmp)
            if not valid:
                print(f"    Validation failed: {err}")
                tmp.unlink(missing_ok=True)
                continue

            tmp.rename(out_path)
            print(f"    Downloaded {size/1e6:.1f} MB  |  {rows:,} rows  → {out_path.name}")
            return True

        except requests.RequestException as e:
            print(f"    Request error: {e}")

        time.sleep(0.5)

    return False


# ── register mode (main use case when download fails) ────────────────────────

def register_existing_file(file_path: pathlib.Path, release_override: str | None) -> None:
    """
    Validate and register a manually downloaded HTS JSON file.
    Copies it to data/raw/hts/ with a canonical name if needed.
    """
    print(f"\nRegistering: {file_path}")

    valid, err, rows = validate_hts_json(file_path)
    if not valid:
        print(f"  ERROR: {err}")
        print("  Make sure you downloaded the JSON (not CSV or XLSX) from hts.usitc.gov/download")
        sys.exit(1)

    print(f"  Validation passed — {rows:,} rows, {file_path.stat().st_size/1e6:.1f} MB")

    # infer release name
    release = release_override or infer_release_from_filename(file_path)
    print(f"  Release: {release}")

    # canonical destination
    dest = RAW_DIR / f"hts_{release}.json"

    if file_path.resolve() != dest.resolve():
        if dest.exists():
            print(f"  Destination already exists: {dest.name}")
            ans = input("  Overwrite? [y/N] ").strip().lower()
            if ans != "y":
                print("  Keeping existing file. Using it as-is.")
                dest = file_path  # use original path
            else:
                import shutil
                shutil.copy2(file_path, dest)
                print(f"  Copied → {dest}")
        else:
            import shutil
            shutil.copy2(file_path, dest)
            print(f"  Copied → {dest}")
    else:
        print(f"  File already in correct location: {dest.name}")

    sha = sha256_of_file(dest)
    write_manifest({
        "hts_release":   release,
        "hts_date":      "",
        "hts_file":      dest.name,
        "hts_sha256":    sha,
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
    })

    print(f"  SHA-256: {sha[:24]}…")
    print(f"\n  Done. Run next:")
    print(f"    python ingestion/parse_hts.py")


# ── check mode ────────────────────────────────────────────────────────────────

def check_mode() -> None:
    latest, _ = discover_latest_release()
    m = read_manifest()
    current = m.get("hts_release", "none")
    on_disk = m.get("hts_file", "none")

    print(f"\n  On disk        : {current}  ({on_disk})")
    print(f"  Latest known   : {latest}")
    if current == latest:
        print("  Status         : up to date")
    else:
        print("  Status         : update available")
        print(f"\n  To update:")
        print(f"    1. Go to https://hts.usitc.gov/download")
        print(f"    2. Download JSON for {latest}")
        print(f"    3. python ingestion/download_hts.py --register <path> --release {latest}")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="HTS downloader + manifest manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Register a file you downloaded manually (most common):
  python ingestion/download_hts.py --register data/raw/hts/hts_2026HTSRev5.json

  # Register with explicit release name:
  python ingestion/download_hts.py --register data/raw/hts/myfile.json --release 2026HTSRev5

  # Check what version is latest (no download):
  python ingestion/download_hts.py --check

  # Attempt auto-download (may get 403 from USITC):
  python ingestion/download_hts.py --force
        """
    )
    ap.add_argument("--register", metavar="FILE",
                    help="Path to a manually downloaded HTS JSON file to register")
    ap.add_argument("--release",  metavar="NAME",
                    help="Release name e.g. 2026HTSRev5 (auto-inferred if not given)")
    ap.add_argument("--check",    action="store_true",
                    help="Check latest release only, no download")
    ap.add_argument("--force",    action="store_true",
                    help="Force auto-download attempt even if already current")
    args = ap.parse_args()

    # ── register mode ─────────────────────────────────────────────────────────
    if args.register:
        register_existing_file(pathlib.Path(args.register), args.release)
        return

    # ── check mode ────────────────────────────────────────────────────────────
    if args.check:
        check_mode()
        return

    # ── auto-download mode ────────────────────────────────────────────────────
    latest_release, latest_date = discover_latest_release()

    m = read_manifest()
    if not args.force and m.get("hts_release") == latest_release:
        print(f"  Already on latest: {latest_release}")
        print("  Use --force to re-download anyway.")
        return

    out_file = RAW_DIR / f"hts_{latest_release}.json"

    if out_file.exists() and not args.force:
        print(f"  File already exists: {out_file.name}")
        print("  Registering it without re-downloading …")
        register_existing_file(out_file, latest_release)
        return

    print(f"\nAttempting download of {latest_release} …")
    success = attempt_download(latest_release, out_file)

    if success:
        sha = sha256_of_file(out_file)
        write_manifest({
            "hts_release":   latest_release,
            "hts_date":      latest_date,
            "hts_file":      out_file.name,
            "hts_sha256":    sha,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        })
        print(f"\n  Next: python ingestion/parse_hts.py")
    else:
        print(f"""
  Auto-download failed (USITC blocks automated requests).

  Manual steps (30 seconds):
    1. Open in browser:  https://hts.usitc.gov/download
    2. Find row:         {latest_release}
    3. Click:            JSON  (not CSV, not XLSX)
    4. Save file to:     data\\raw\\hts\\hts_{latest_release}.json
    5. Run:              python ingestion/download_hts.py --register data\\raw\\hts\\hts_{latest_release}.json
        """)
        sys.exit(1)


if __name__ == "__main__":
    main()