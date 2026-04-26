"""
ingestion/chunker.py  — Phase 2, Step 1
-----------------------------------------
Hybrid chunking strategy for HTS nodes.

TWO chunk types produced:

  TYPE 1 — node chunks (one per codeable node, 29,583 total)
    Direct embedding of each node's chunk_text.
    Best for: specific lookups — "duty rate for 8471.30.01.00"
    Metadata filters: chapter, heading, subheading, node_type, hts_release

  TYPE 2 — heading summary chunks (one per heading, ~961 total)
    Combines heading description + all its direct children (subheadings
    and tariff items) into a single rich text block.
    Best for: broad semantic search — "laptop computer tariff"
    A query about "laptops" hits the heading chunk which mentions
    all variants (portable, desktop, <10kg etc.) in one place.

Together these give you both granular lookup and broad semantic coverage
without needing to embed the same content twice inefficiently.

Output:
  data/processed/chunks/chunks_node.jsonl      — 29,583 node chunks
  data/processed/chunks/chunks_heading.jsonl   — ~961 heading chunks
  data/processed/chunks/chunk_stats.json       — counts + token estimates

Each output record:
{
  "chunk_id":      "node_8471300100",
  "chunk_type":    "node",               # or "heading_summary"
  "chunk_text":    "HTS 8471.30.0100: ...",
  "hts_code":      "8471.30.0100",       # empty for heading summaries
  "heading":       "8471",
  "chapter":       "84",
  "subheading":    "8471.30",
  "node_type":     "statistical",        # heading_summary for type 2
  "general_rate":  "Free",
  "special_rate":  "Free (A+,AU,...)",
  "hts_release":   "2026HTSRev6",
  "doc_type":      "hts",
  "token_est":     42                    # rough token count for budget tracking
}

Run:
    python ingestion/chunker.py
    python ingestion/chunker.py --no-summaries   # node chunks only
    python ingestion/chunker.py --min-rate-only  # only nodes with duty rates
"""

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

NODES_FILE  = pathlib.Path("data/processed/hts/hts_nodes.jsonl")
OUT_DIR     = pathlib.Path("data/processed/chunks")
OUT_NODES   = OUT_DIR / "chunks_node.jsonl"
OUT_HEADS   = OUT_DIR / "chunks_heading.jsonl"
OUT_STATS   = OUT_DIR / "chunk_stats.json"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── token estimator (no tiktoken needed — rough 4 chars/token) ───────────────

def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ── chunk id builder ──────────────────────────────────────────────────────────

def make_chunk_id(prefix: str, code: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]", "_", code)
    return f"{prefix}_{safe}"


# ── load nodes ────────────────────────────────────────────────────────────────

def load_nodes(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: {path} not found.")
        print("  Run: python ingestion/parse_hts.py  first")
        sys.exit(1)
    nodes = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                nodes.append(json.loads(line))
    print(f"Loaded {len(nodes):,} nodes from {path}")
    return nodes


# ── TYPE 1 — node chunks ──────────────────────────────────────────────────────

def make_node_chunks(nodes: list[dict], min_rate_only: bool) -> list[dict]:
    """
    One chunk per node. Uses the chunk_text already built by parse_hts.py.
    Optionally filter to only nodes that have a general duty rate set —
    useful for a smaller, higher-signal corpus during development.
    """
    chunks = []
    skipped = 0

    for node in nodes:
        chunk_text = node.get("chunk_text", "").strip()
        if not chunk_text:
            skipped += 1
            continue

        if min_rate_only and not node.get("general_rate"):
            skipped += 1
            continue

        chunk: dict = {
            "chunk_id":    make_chunk_id("node", node["hts_code"]),
            "chunk_type":  "node",
            "chunk_text":  chunk_text,
            "hts_code":    node["hts_code"],
            "heading":     node.get("heading",    ""),
            "chapter":     node.get("chapter",    ""),
            "subheading":  node.get("subheading", ""),
            "node_type":   node.get("node_type",  ""),
            "general_rate":  node.get("general_rate",  ""),
            "special_rate":  node.get("special_rate",  ""),
            "other_rate":    node.get("other_rate",    ""),
            "unit_of_qty":   node.get("unit_of_qty",   ""),
            "footnotes_text": node.get("footnotes_text", ""),
            "hts_release": node.get("hts_release", ""),
            "doc_type":    "hts",
            "token_est":   est_tokens(chunk_text),
        }
        chunks.append(chunk)

    print(f"  Node chunks   : {len(chunks):,}  (skipped {skipped:,})")
    return chunks


# ── TYPE 2 — heading summary chunks ──────────────────────────────────────────

def make_heading_chunks(nodes: list[dict]) -> list[dict]:
    """
    One chunk per HTS heading (4-digit code).
    Groups the heading node + all its children into a rich summary text.

    Structure of summary chunk_text:
      HTS Heading 8471 — Automatic data processing machines and units thereof:
      Subheadings and rates:
      • 8471.30 (Portable machines, ≤10kg): General: Free. Special: Free (A+,AU,...)
      • 8471.41 (Other machines, ≤10kg): General: Free.
      • 8471.49 (Other): General: Free.
      • 8471.50 (Processing units): General: Free.
      [+12 statistical lines]
    """
    # group nodes by heading
    by_heading: dict[str, list[dict]] = defaultdict(list)
    heading_nodes: dict[str, dict]    = {}

    for node in nodes:
        h = node.get("heading", "")
        if not h:
            continue
        by_heading[h].append(node)
        if node.get("node_type") == "heading":
            heading_nodes[h] = node

    chunks = []

    for heading, children in sorted(by_heading.items()):
        # heading description
        head_node = heading_nodes.get(heading)
        head_desc = head_node["description"] if head_node else ""

        # collect subheadings and tariff items (skip pure statistical to keep chunk short)
        rate_lines = []
        stat_count = 0

        for child in sorted(children, key=lambda x: x["hts_code"]):
            ntype = child.get("node_type", "")
            desc  = child.get("description", "")
            code  = child["hts_code"]
            rate  = child.get("general_rate", "")
            special = child.get("special_rate", "")
            units = child.get("unit_of_qty", "")

            if ntype == "heading":
                continue  # heading itself handled above

            if ntype == "statistical":
                stat_count += 1
                continue   # too granular for summary — just count them

            # subheading or tariff_item — include with rates
            parts = [f"• {code}"]
            if desc:
                parts.append(f"({desc[:60]})")
            if rate:
                parts.append(f"General: {rate}.")
            if special:
                s = special[:60] + "…" if len(special) > 60 else special
                parts.append(f"Special: {s}.")
            if units:
                parts.append(f"Unit: {units}.")

            rate_lines.append(" ".join(parts))

        if not rate_lines and stat_count == 0:
            continue

        # build summary text
        lines = [f"HTS Heading {heading}"]
        if head_desc:
            lines.append(f"— {head_desc}:")
        lines.append("")

        if rate_lines:
            lines.append("Subheadings and tariff items:")
            lines.extend(rate_lines[:15])  # cap at 15 lines — keeps under 2000 chars
            if len(rate_lines) > 15:
                lines.append(f"  [+{len(rate_lines)-15} more items]")

        if stat_count:
            lines.append(f"[{stat_count} statistical subdivisions]")

        summary_text = "\n".join(lines)

        # inherit best available rate from children
        all_rates    = [c.get("general_rate","") for c in children if c.get("general_rate")]
        all_specials = [c.get("special_rate","") for c in children if c.get("special_rate")]
        release      = children[0].get("hts_release","") if children else ""
        chapter      = children[0].get("chapter","")     if children else ""

        chunk: dict = {
            "chunk_id":    make_chunk_id("heading", heading),
            "chunk_type":  "heading_summary",
            "chunk_text":  summary_text,
            "hts_code":    "",
            "heading":     heading,
            "chapter":     chapter,
            "subheading":  "",
            "node_type":   "heading_summary",
            "general_rate":  all_rates[0]    if all_rates    else "",
            "special_rate":  all_specials[0] if all_specials else "",
            "other_rate":    "",
            "unit_of_qty":   "",
            "footnotes_text": "",
            "child_count": len(children),
            "hts_release": release,
            "doc_type":    "hts",
            "token_est":   est_tokens(summary_text),
        }
        chunks.append(chunk)

    print(f"  Heading chunks: {len(chunks):,}")
    return chunks


# ── write + stats ─────────────────────────────────────────────────────────────

def write_jsonl(records: list[dict], out: pathlib.Path) -> None:
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  Wrote {len(records):,} records → {out}")


def print_and_save_stats(node_chunks: list[dict],
                          head_chunks: list[dict]) -> None:
    all_chunks = node_chunks + head_chunks
    total      = len(all_chunks)
    tok_total  = sum(c["token_est"] for c in all_chunks)
    tok_avg    = tok_total // total if total else 0

    # token distribution
    under50  = sum(1 for c in all_chunks if c["token_est"] < 50)
    under100 = sum(1 for c in all_chunks if c["token_est"] < 100)
    over200  = sum(1 for c in all_chunks if c["token_est"] >= 200)

    # chapter distribution
    from collections import Counter
    chapters = Counter(c["chapter"] for c in all_chunks if c["chapter"])

    print(f"\n── Chunk stats ───────────────────────────────────────────────────")
    print(f"  Node chunks      : {len(node_chunks):,}")
    print(f"  Heading chunks   : {len(head_chunks):,}")
    print(f"  Total chunks     : {total:,}")
    print(f"  Est. total tokens: {tok_total:,}")
    print(f"  Avg tokens/chunk : {tok_avg}")
    print(f"  <50 tokens       : {under50:,}  (very short — mostly leaf nodes)")
    print(f"  <100 tokens      : {under100:,}")
    print(f"  ≥200 tokens      : {over200:,}  (heading summaries)")
    print(f"  Chapters covered : {len(chapters)}")

    # cost estimate for embedding
    # text-embedding-3-small: $0.02 per 1M tokens
    cost_oai = tok_total * 0.00002 / 1000
    print(f"\n── Embedding cost estimate ───────────────────────────────────────")
    print(f"  OpenAI text-embedding-3-small : ${cost_oai:.4f}  ({tok_total:,} tokens)")
    print(f"  Ollama nomic-embed-text       : $0.0000  (free, local)")

    # sample chunks
    print(f"\n── Sample node chunk ────────────────────────────────────────────")
    rated = [c for c in node_chunks if c["general_rate"]]
    if rated:
        s = rated[0]
        print(f"  chunk_id   : {s['chunk_id']}")
        print(f"  hts_code   : {s['hts_code']}")
        print(f"  chapter    : {s['chapter']}")
        print(f"  node_type  : {s['node_type']}")
        print(f"  general    : {s['general_rate']}")
        print(f"  token_est  : {s['token_est']}")
        ct = s['chunk_text']
        print(f"  chunk_text : {ct[:200]}{'…' if len(ct)>200 else ''}")

    print(f"\n── Sample heading chunk ─────────────────────────────────────────")
    if head_chunks:
        s = head_chunks[0]
        print(f"  chunk_id   : {s['chunk_id']}")
        print(f"  heading    : {s['heading']}")
        print(f"  children   : {s.get('child_count',0)}")
        print(f"  token_est  : {s['token_est']}")
        ct = s['chunk_text']
        print(f"  chunk_text :\n{ct[:400]}{'…' if len(ct)>400 else ''}")

    OUT_STATS.write_text(json.dumps({
        "node_chunks":    len(node_chunks),
        "heading_chunks": len(head_chunks),
        "total_chunks":   total,
        "total_tokens":   tok_total,
        "avg_tokens":     tok_avg,
        "chapters":       len(chapters),
        "cost_openai_usd": round(cost_oai, 6),
        "chunked_at":     datetime.now(timezone.utc).isoformat(),
    }, indent=2))


# ── entry ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Hybrid chunker for HTS nodes")
    ap.add_argument("--no-summaries",  action="store_true",
                    help="Skip heading summary chunks — node chunks only")
    ap.add_argument("--min-rate-only", action="store_true",
                    help="Only emit node chunks that have a general duty rate")
    args = ap.parse_args()

    nodes = load_nodes(NODES_FILE)

    print("\nBuilding node chunks…")
    node_chunks = make_node_chunks(nodes, min_rate_only=args.min_rate_only)

    head_chunks: list[dict] = []
    if not args.no_summaries:
        print("Building heading summary chunks…")
        head_chunks = make_heading_chunks(nodes)

    print()
    write_jsonl(node_chunks, OUT_NODES)
    if head_chunks:
        write_jsonl(head_chunks, OUT_HEADS)

    print_and_save_stats(node_chunks, head_chunks)

    print(f"\n── Done ──────────────────────────────────────────────────────────")
    print(f"  Next: python stores/vector_store.py")


if __name__ == "__main__":
    main()