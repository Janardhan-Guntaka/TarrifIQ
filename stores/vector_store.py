"""
stores/vector_store.py  — Phase 2, Step 2
------------------------------------------
Loads HTS chunks into ChromaDB using Ollama nomic-embed-text embeddings.

Two collections:
  hts_nodes       — 29,583 individual node chunks (granular lookup)
  hts_headings    — 1,262 heading summary chunks  (broad semantic search)

ChromaDB persists to disk at .chroma/ — no server needed.
Re-running is safe — existing collections are cleared and rebuilt.

Embedding model: nomic-embed-text via Ollama (free, local, 768-dim)
  Install: https://ollama.ai
  Pull:    ollama pull nomic-embed-text

Usage:
  # Build / rebuild both collections
  python stores/vector_store.py

  # Query interactively to test retrieval
  python stores/vector_store.py --query "laptop computer tariff rate"

  # Query with chapter filter
  python stores/vector_store.py --query "electric motor" --chapter 85

  # Rebuild only one collection
  python stores/vector_store.py --collection nodes
  python stores/vector_store.py --collection headings
"""

import argparse
import json
import pathlib
import sys
import time
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

# ── paths ─────────────────────────────────────────────────────────────────────
CHUNKS_NODE = pathlib.Path("data/processed/chunks/chunks_node.jsonl")
CHUNKS_HEAD = pathlib.Path("data/processed/chunks/chunks_heading.jsonl")
CHROMA_DIR  = pathlib.Path(".chroma")

# ── collection names ──────────────────────────────────────────────────────────
COL_NODES    = "hts_nodes"
COL_HEADINGS = "hts_headings"

# ── embedding config ──────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434"
EMBED_MODEL  = "nomic-embed-text"
BATCH_SIZE   = 50   # chunks per embedding call — nomic handles 50 well
MAX_CHARS    = 6000 # nomic-embed-text context = 8192 tokens ~ 6000 chars safe limit


# ── helpers ───────────────────────────────────────────────────────────────────

def load_jsonl(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        print(f"ERROR: {path} not found — run ingestion/chunker.py first")
        sys.exit(1)
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def get_client() -> chromadb.Client:
    CHROMA_DIR.mkdir(exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_embedding_fn() -> OllamaEmbeddingFunction:
    return OllamaEmbeddingFunction(
        url=f"{OLLAMA_URL}/api/embeddings",
        model_name=EMBED_MODEL,
    )


def test_ollama(embed_fn: OllamaEmbeddingFunction) -> bool:
    """Verify Ollama is running and nomic-embed-text is available."""
    print(f"Testing Ollama ({EMBED_MODEL}) …")
    try:
        result = embed_fn(["test"])
        if result and len(result[0]) > 0:
            print(f"  OK — embedding dim: {len(result[0])}\n")
            return True
    except Exception as e:
        print(f"  FAILED: {e}")
        print(f"\n  Fix:")
        print(f"    1. Is Ollama running?  Start it: ollama serve")
        print(f"    2. Is model pulled?    Run:      ollama pull nomic-embed-text")
        print(f"    3. Is port correct?    Expected: {OLLAMA_URL}")
        return False
    return False


# ── metadata builder ──────────────────────────────────────────────────────────

def build_metadata(chunk: dict) -> dict:
    """
    ChromaDB metadata must be flat dict with str/int/float/bool values only.
    Lists and None are not allowed — convert to empty string.
    """
    return {
        "chunk_type":     chunk.get("chunk_type",     ""),
        "hts_code":       chunk.get("hts_code",       ""),
        "heading":        chunk.get("heading",        ""),
        "chapter":        chunk.get("chapter",        ""),
        "subheading":     chunk.get("subheading",     ""),
        "node_type":      chunk.get("node_type",      ""),
        "general_rate":   chunk.get("general_rate",   ""),
        "special_rate":   chunk.get("special_rate",   "")[:200],  # cap length
        "other_rate":     chunk.get("other_rate",     ""),
        "unit_of_qty":    chunk.get("unit_of_qty",    ""),
        "hts_release":    chunk.get("hts_release",    ""),
        "doc_type":       chunk.get("doc_type",       "hts"),
        "token_est":      chunk.get("token_est",      0),
        "child_count":    chunk.get("child_count",    0),
    }


# ── batch upsert ──────────────────────────────────────────────────────────────

def upsert_chunks(
    collection: chromadb.Collection,
    chunks: list[dict],
    label: str,
) -> None:
    total   = len(chunks)
    batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    done    = 0

    for i in range(0, total, BATCH_SIZE):
        batch     = chunks[i : i + BATCH_SIZE]
        ids       = [c["chunk_id"]   for c in batch]
        documents = [c["chunk_text"][:MAX_CHARS] for c in batch]  # truncate to model limit
        metadatas = [build_metadata(c) for c in batch]

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )
        done += len(batch)
        batch_num = i // BATCH_SIZE + 1
        pct = int(100 * done / total)
        bar = "=" * int(pct / 5)
        print(f"\r  {label}: [{bar:<20}] {pct:3d}%  {done:,}/{total:,}", end="", flush=True)

    print()  # newline after progress bar


# ── build collection ──────────────────────────────────────────────────────────

def build_collection(
    client:   chromadb.Client,
    embed_fn: OllamaEmbeddingFunction,
    name:     str,
    chunks:   list[dict],
) -> chromadb.Collection:

    # delete + recreate for clean rebuild
    try:
        client.delete_collection(name)
        print(f"  Cleared existing collection: {name}")
    except Exception:
        pass

    collection = client.create_collection(
        name=name,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},   # cosine similarity
    )

    start = time.time()
    upsert_chunks(collection, chunks, name)
    elapsed = time.time() - start

    count = collection.count()
    print(f"  Indexed {count:,} chunks in {elapsed:.1f}s "
          f"({count/elapsed:.0f} chunks/sec)")
    return collection


# ── query helper ──────────────────────────────────────────────────────────────

def query_collection(
    collection: chromadb.Collection,
    query:      str,
    n:          int   = 5,
    chapter:    str   = "",
    node_type:  str   = "",
) -> list[dict]:
    """
    Query a collection with optional metadata filters.
    Returns list of result dicts with document, metadata, distance.
    """
    where: dict[str, Any] = {}

    if chapter and node_type:
        where = {"$and": [
            {"chapter":   {"$eq": chapter}},
            {"node_type": {"$eq": node_type}},
        ]}
    elif chapter:
        where = {"chapter": {"$eq": chapter}}
    elif node_type:
        where = {"node_type": {"$eq": node_type}}

    kwargs: dict[str, Any] = {
        "query_texts": [query],
        "n_results":   n,
        "include":     ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    output = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        output.append({
            "document": doc,
            "metadata": meta,
            "score":    round(1 - dist, 4),  # cosine similarity (1=identical)
        })
    return output


# ── interactive test ──────────────────────────────────────────────────────────

def run_query(query: str, chapter: str = "") -> None:
    client   = get_client()
    embed_fn = get_embedding_fn()

    print(f'\nQuery: "{query}"')
    if chapter:
        print(f'Filter: chapter={chapter}')
    print()

    # search headings first (broad)
    try:
        col_head = client.get_collection(COL_HEADINGS, embedding_function=embed_fn)
        head_results = query_collection(col_head, query, n=3, chapter=chapter)
        print("── Heading matches (broad) ───────────────────────────────────────")
        for r in head_results:
            m = r["metadata"]
            print(f"  [{r['score']:.3f}] Heading {m['heading']}  "
                  f"chapter={m['chapter']}  rate={m['general_rate']}")
            # print first 2 lines of chunk text
            lines = r["document"].split("\n")[:3]
            for line in lines:
                if line.strip():
                    print(f"          {line.strip()[:100]}")
            print()
    except Exception as e:
        print(f"  headings collection not found: {e}")

    # search nodes (granular)
    try:
        col_node = client.get_collection(COL_NODES, embedding_function=embed_fn)
        # filter to tariff_item and subheading for most useful results
        node_results = query_collection(col_node, query, n=5, chapter=chapter)
        print("── Node matches (granular) ───────────────────────────────────────")
        for r in node_results:
            m = r["metadata"]
            print(f"  [{r['score']:.3f}] {m['hts_code']:<16} "
                  f"type={m['node_type']:<12} "
                  f"rate={m['general_rate'] or '—':<8} "
                  f"ch={m['chapter']}")
            # first line of chunk text (description part)
            first_line = r["document"].split(".")[0]
            print(f"          {first_line[:100]}")
            print()
    except Exception as e:
        print(f"  nodes collection not found: {e}")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Build / query HTS vector store")
    ap.add_argument("--query",      metavar="TEXT",
                    help="Run a test query against the built collections")
    ap.add_argument("--chapter",    metavar="CH",  default="",
                    help="Filter query results to a specific chapter e.g. 84")
    ap.add_argument("--collection", choices=["nodes", "headings", "both"],
                    default="both", help="Which collection to build")
    ap.add_argument("--resume-headings", action="store_true",
                    help="Only rebuild hts_headings (nodes already built)")
    ap.add_argument("--skip-build", action="store_true",
                    help="Skip building — only run --query")
    args = ap.parse_args()

    # ── query-only mode ───────────────────────────────────────────────────────
    if args.query and args.skip_build:
        run_query(args.query, chapter=args.chapter)
        return

    # ── build mode ────────────────────────────────────────────────────────────
    if not args.skip_build:
        embed_fn = get_embedding_fn()
        if not test_ollama(embed_fn):
            sys.exit(1)

        client = get_client()

        # --resume-headings skips nodes (already built) and only does headings
        build_nodes    = not args.resume_headings and args.collection in ("nodes", "both")
        build_headings = args.resume_headings     or args.collection in ("headings", "both")

        if build_nodes:
            print(f"Loading node chunks …")
            node_chunks = load_jsonl(CHUNKS_NODE)
            print(f"Building collection: {COL_NODES}  ({len(node_chunks):,} chunks)\n")
            build_collection(client, embed_fn, COL_NODES, node_chunks)
            print()

        if build_headings:
            print(f"Loading heading chunks …")
            head_chunks = load_jsonl(CHUNKS_HEAD)
            print(f"Building collection: {COL_HEADINGS}  ({len(head_chunks):,} chunks)\n")
            build_collection(client, embed_fn, COL_HEADINGS, head_chunks)
            print()

        print("── Vector store ready ────────────────────────────────────────────")
        print(f"  Location : {CHROMA_DIR.resolve()}")

        client2 = get_client()
        for col_name in [COL_NODES, COL_HEADINGS]:
            try:
                col = client2.get_collection(col_name)
                print(f"  {col_name:<20}: {col.count():,} chunks")
            except Exception:
                pass

        print()
        print("  Test your store:")
        print('  python stores/vector_store.py --skip-build --query "laptop computer"')
        print('  python stores/vector_store.py --skip-build --query "electric motor" --chapter 85')

    # ── run query after build if provided ─────────────────────────────────────
    if args.query:
        run_query(args.query, chapter=args.chapter)


if __name__ == "__main__":
    main()