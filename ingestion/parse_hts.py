"""
ingestion/parse_hts.py  — Phase 1, Step 2
------------------------------------------
Parses the USITC full HTS JSON (any revision, 2025/2026+).

Exact source structure (confirmed from live 2026 Rev 5):
  Root: JSON array  [{ ... }, ...]
  Keys per row:
    htsno            str   — HTS code e.g. "8471.30.01.00" (empty for label rows)
    indent           str   — nesting depth "0".."5"
    description      str   — product description
    superior         str   — "true" if label-only row with no code
    units            list  — ["No."] or ["No.", "kg"] or []
    general          str   — MFN duty rate e.g. "Free" or "6.8%"
    special          str   — FTA rates e.g. "Free (A+,AU,BH,CL...)"
    other            str   — Column 2 (non-MFN) rate
    footnotes        list  — [{"columns":["general"],"value":"See 9903.88.15.","type":"endnote"}]
    quotaQuantity    str
    additionalDuties str   — also addiitionalDuties (USITC typo — both handled)

Row types:
  1. htsno != ""                        → codeable node → write to JSONL
  2. htsno == "" + superior == "true"   → context label → track ancestors
  3. htsno == "" + no superior          → spacer        → skip (update context if has desc)

Context inheritance:
  Leaf nodes like description="Female" under "Purebred breeding > Dairy" become:
  chunk_text = "HTS 0102.21.00.20: Purebred breeding animals > Dairy > Female. General: Free."
  This makes semantic search work on one-word leaf descriptions.

Future-proof features:
  - Reads latest file from manifest (data/manifest.json) — no hardcoded filename
  - Falls back to newest .json in data/raw/hts/ if manifest absent
  - Stores hts_release in every output node for version tracking
  - Idempotent — re-running with a new revision file safely overwrites JSONL
  - Writes parse_stats.json for monitoring / CI checks

Outputs:
  data/processed/hts/hts_nodes.jsonl
  data/processed/hts/general_notes.jsonl
  data/processed/hts/parse_stats.json

Run:
    python ingestion/parse_hts.py
    python ingestion/parse_hts.py --file data/raw/hts/hts_2026HTSRev5.json
"""

import argparse
import json
import pathlib
import re
import sys
from collections import Counter
from datetime import datetime, timezone

RAW_DIR   = pathlib.Path("data/raw/hts")
PROCESSED = pathlib.Path("data/processed/hts")
OUT_NODES = PROCESSED / "hts_nodes.jsonl"
OUT_NOTES = PROCESSED / "general_notes.jsonl"
OUT_STATS = PROCESSED / "parse_stats.json"
MANIFEST  = pathlib.Path("data/manifest.json")
PROCESSED.mkdir(parents=True, exist_ok=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def clean(val) -> str:
    return " ".join(str(val).split()) if val else ""

def units_to_str(u) -> str:
    if isinstance(u, list):
        return " / ".join(s for s in u if s)
    return clean(u)

def footnotes_to_str(fn) -> str:
    if not isinstance(fn, list):
        return ""
    return " | ".join(
        clean(f["value"]) for f in fn
        if isinstance(f, dict) and f.get("value")
    )

def infer_node_type(code: str) -> str:
    d = len(re.sub(r"\D", "", code))
    if d <= 2:  return "chapter"
    if d <= 4:  return "heading"
    if d <= 6:  return "subheading"
    if d <= 8:  return "tariff_item"
    return "statistical"

def decompose(code: str) -> dict:
    d = re.sub(r"\D", "", code)
    return {
        "chapter":    d[:2]  if len(d) >= 2 else "",
        "heading":    d[:4]  if len(d) >= 4 else "",
        "subheading": f"{d[:4]}.{d[4:6]}" if len(d) >= 6 else "",
    }

def is_general_note(htsno: str, desc: str) -> bool:
    return not htsno and bool(re.match(r"^\d+\.", desc.strip()))


# ── context tracker ───────────────────────────────────────────────────────────

class ContextTracker:
    def __init__(self):
        self._ctx: dict[int, str] = {}

    def update(self, indent: int, desc: str) -> None:
        self._ctx[indent] = desc
        for k in list(self._ctx):
            if k > indent:
                del self._ctx[k]

    def ancestors(self, indent: int) -> list[str]:
        return [self._ctx[i] for i in range(indent) if i in self._ctx]


# ── chunk text ────────────────────────────────────────────────────────────────

def build_chunk(node: dict, ancestors: list[str]) -> str:
    parts = [f"HTS {node['hts_code']}:"]

    desc = node["description"]
    if ancestors:
        ctx   = " > ".join(ancestors[-2:])
        label = f"{ctx} > {desc}" if desc else ctx
    else:
        label = desc
    if label:
        parts.append(label.rstrip(":") + ".")

    if node["general_rate"]:
        parts.append(f"General duty rate: {node['general_rate']}.")
    if node["special_rate"]:
        fta = node["special_rate"]
        parts.append(f"Special (FTA) rate: {fta[:100]}{'…' if len(fta)>100 else ''}.")
    if node["other_rate"]:
        parts.append(f"Column 2 rate: {node['other_rate']}.")
    if node["unit_of_qty"]:
        parts.append(f"Unit: {node['unit_of_qty']}.")
    if node["footnotes_text"]:
        parts.append(f"Note: {node['footnotes_text']}.")

    return " ".join(parts)


# ── file resolution ───────────────────────────────────────────────────────────

def resolve_input(file_arg: str | None) -> pathlib.Path:
    if file_arg:
        p = pathlib.Path(file_arg)
        if not p.exists():
            print(f"ERROR: File not found: {p}")
            sys.exit(1)
        return p

    if MANIFEST.exists():
        m = json.loads(MANIFEST.read_text())
        fname = m.get("hts_file")
        if fname:
            p = RAW_DIR / fname
            if p.exists():
                print(f"  Using file from manifest: {p.name}")
                return p
            print(f"  WARNING: manifest points to {fname} but file missing — scanning folder")

    files = sorted(RAW_DIR.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        print(f"ERROR: No .json files found in {RAW_DIR}/")
        print("  Run: python ingestion/download_hts.py")
        sys.exit(1)
    print(f"  Auto-selected newest file: {files[0].name}")
    return files[0]


def resolve_release(args_release: str | None, src_file: pathlib.Path) -> str:
    if args_release:
        return args_release
    if MANIFEST.exists():
        m = json.loads(MANIFEST.read_text())
        r = m.get("hts_release", "")
        if r:
            return r
    m = re.search(r"(\d{4}HTS\w+)", src_file.stem, re.IGNORECASE)
    return m.group(1) if m else src_file.stem


# ── parser ────────────────────────────────────────────────────────────────────

def parse(path: pathlib.Path, release: str) -> tuple[list[dict], list[dict]]:
    print(f"\nParsing {path.name}  ({path.stat().st_size / 1e6:.1f} MB) …")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    # unwrap dict root if needed
    if isinstance(raw, dict):
        for key in ("HTSData", "htsData", "data", "rows", "results"):
            if key in raw and isinstance(raw[key], list):
                raw = raw[key]
                break
        else:
            print(f"  ERROR: dict root with unknown keys: {list(raw.keys())[:6]}")
            sys.exit(1)

    if not isinstance(raw, list):
        print(f"  ERROR: expected list at root, got {type(raw)}")
        sys.exit(1)

    print(f"  Total rows in source: {len(raw):,}")

    tracker  = ContextTracker()
    nodes:   list[dict] = []
    notes:   list[dict] = []
    n_label  = 0
    n_blank  = 0

    for row in raw:
        if not isinstance(row, dict):
            continue

        htsno    = clean(row.get("htsno", ""))
        indent   = int(row.get("indent") or 0)
        desc     = clean(row.get("description", ""))
        superior = str(row.get("superior", "")).lower() == "true"

        # General Note rows
        if is_general_note(htsno, desc):
            notes.append({
                "indent":      indent,
                "description": desc,
                "doc_type":    "hts_general_note",
                "hts_release": release,
                "source_file": path.name,
                "chunk_text":  f"HTS General Note: {desc}",
            })
            tracker.update(indent, desc)
            continue

        # Context label rows (no htsno, superior=true)
        if not htsno and superior:
            if desc:
                tracker.update(indent, desc)
            n_label += 1
            continue

        # Blank spacer rows
        if not htsno:
            if desc:
                tracker.update(indent, desc)
            n_blank += 1
            continue

        # Codeable node
        ancestors  = tracker.ancestors(indent)
        add_duties = clean(
            row.get("additionalDuties") or row.get("addiitionalDuties") or ""
        )

        node: dict = {
            "hts_code":          htsno,
            "indent_level":      indent,
            "description":       desc,
            "unit_of_qty":       units_to_str(row.get("units")),
            "general_rate":      clean(row.get("general",       "")),
            "special_rate":      clean(row.get("special",       "")),
            "other_rate":        clean(row.get("other",         "")),
            "quota_quantity":    clean(row.get("quotaQuantity", "")),
            "additional_duties": add_duties,
            "footnotes_text":    footnotes_to_str(row.get("footnotes")),
            "ancestor_path":     ancestors,
            "node_type":         infer_node_type(htsno),
            "doc_type":          "hts",
            "hts_release":       release,
            "source_file":       path.name,
            **decompose(htsno),
        }
        node["chunk_text"] = build_chunk(node, ancestors)

        tracker.update(indent, desc)
        nodes.append(node)

    print(f"  → {len(nodes):,} codeable nodes | "
          f"{len(notes):,} general note rows | "
          f"{n_label:,} label rows | "
          f"{n_blank:,} blank rows skipped")

    return nodes, notes


# ── output + stats ────────────────────────────────────────────────────────────

def write_jsonl(records: list[dict], out: pathlib.Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(records):,} records → {out}")


def print_and_save_stats(nodes: list[dict], release: str) -> None:
    total       = len(nodes)
    type_counts = Counter(n["node_type"] for n in nodes)
    chapters    = sorted({n["chapter"] for n in nodes if n["chapter"]})
    has_rate    = sum(1 for n in nodes if n["general_rate"])
    has_special = sum(1 for n in nodes if n["special_rate"])
    has_units   = sum(1 for n in nodes if n["unit_of_qty"])
    has_fn      = sum(1 for n in nodes if n["footnotes_text"])
    has_anc     = sum(1 for n in nodes if n["ancestor_path"])

    print(f"\n── Stats ({release}) ──────────────────────────────────────────────")
    print(f"  Total codeable nodes  : {total:,}")
    print(f"  Node types            : {dict(type_counts)}")
    print(f"  Chapters              : {len(chapters)} total  (e.g. {chapters[:8]}…)")
    print(f"  Have general_rate     : {has_rate:,}  ({100*has_rate//total if total else 0}%)")
    print(f"  Have special/FTA rate : {has_special:,}  ({100*has_special//total if total else 0}%)")
    print(f"  Have unit_of_qty      : {has_units:,}")
    print(f"  Have footnotes        : {has_fn:,}")
    print(f"  Have ancestor context : {has_anc:,}  ({100*has_anc//total if total else 0}%)")

    OUT_STATS.write_text(json.dumps({
        "release":       release,
        "total_nodes":   total,
        "node_types":    dict(type_counts),
        "chapter_count": len(chapters),
        "pct_has_rate":  100*has_rate//total if total else 0,
        "parsed_at":     datetime.now(timezone.utc).isoformat(),
    }, indent=2))


def print_sample(nodes: list[dict]) -> None:
    print("\n── Sample (one per node type) ────────────────────────────────────")
    by_type: dict[str, dict] = {}
    for n in nodes:
        if n["node_type"] not in by_type:
            by_type[n["node_type"]] = n

    for nt in ["heading", "subheading", "tariff_item", "statistical"]:
        s = by_type.get(nt)
        if not s:
            continue
        print(f"\n  [{nt.upper()}]  {s['hts_code']}")
        print(f"  description   : {s['description']}")
        print(f"  ancestor_path : {s['ancestor_path'][-2:]}")
        print(f"  general_rate  : {s['general_rate']}")
        sr = s['special_rate']
        print(f"  special_rate  : {sr[:70]}{'…' if len(sr)>70 else ''}")
        print(f"  units         : {s['unit_of_qty']}")
        print(f"  footnotes     : {s['footnotes_text']}")
        ct = s['chunk_text']
        print(f"  chunk_text    : {ct[:240]}{'…' if len(ct)>240 else ''}")


# ── entry ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Parse USITC HTS JSON → JSONL")
    ap.add_argument("--file",    help="Path to HTS JSON file (default: auto-detected)")
    ap.add_argument("--release", help="Release label e.g. 2026HTSRev5 (default: from manifest)")
    args = ap.parse_args()

    src  = resolve_input(args.file)
    rel  = resolve_release(args.release, src)

    nodes, notes = parse(src, rel)

    if not nodes:
        print("\nNo nodes produced — check the JSON structure above.")
        sys.exit(1)

    print()
    write_jsonl(nodes, OUT_NODES)
    if notes:
        write_jsonl(notes, OUT_NOTES)

    print_and_save_stats(nodes, rel)
    print_sample(nodes)

    print("\n── Done ──────────────────────────────────────────────────────────")
    print("  Next: python -m backend.scripts.ingest_local --version <VERSION> --skip-parse --activate")


if __name__ == "__main__":
    main()