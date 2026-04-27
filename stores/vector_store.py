"""
stores/vector_store.py
-----------------------
ChromaDB vector store for HTS chunks.

Embedding model:
  Cloud / Streamlit: OpenAI text-embedding-3-small (when OPENAI_API_KEY set)
  Local dev:         Ollama nomic-embed-text (fallback when no key)

IMPORTANT — rebuild required when switching embedding models:
  The .chroma/ collections must be built with the SAME model used for queries.
  After setting OPENAI_API_KEY, rebuild with:
    python stores/vector_store.py

Two collections:
  hts_nodes    — 29,583 individual HTS nodes (granular lookup)
  hts_headings — 1,262 heading summaries (broad semantic search)
"""

import argparse
import json
import os
import pathlib
import sys
import time
from typing import Any

import chromadb

# ── paths — absolute, work from any working directory ─────────────────────────
_HERE       = pathlib.Path(__file__).parent.parent.resolve()
CHUNKS_NODE = _HERE / "data/processed/chunks/chunks_node.jsonl"
CHUNKS_HEAD = _HERE / "data/processed/chunks/chunks_heading.jsonl"
CHROMA_DIR  = _HERE / ".chroma"

# ── collection names ───────────────────────────────────────────────────────────
COL_NODES    = "hts_nodes"
COL_HEADINGS = "hts_headings"

# ── embedding settings ─────────────────────────────────────────────────────────
OPENAI_EMBED_MODEL = "text-embedding-3-small"   # 1536-dim, $0.02/1M tokens
OLLAMA_URL         = "http://localhost:11434"
OLLAMA_EMBED_MODEL = "nomic-embed-text"          # 768-dim, free local
BATCH_SIZE         = 50
MAX_CHARS          = 2000


# ── embedding function factory ─────────────────────────────────────────────────

def get_embedding_fn():
    """
    Returns OpenAI embedding function when OPENAI_API_KEY is set,
    otherwise falls back to Ollama for local development.

    NOTE: Collections MUST be rebuilt when switching between models.
    OpenAI produces 1536-dim vectors; Ollama nomic produces 768-dim.
    Mixing them causes dimension mismatch errors in ChromaDB.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")

    if api_key:
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        return OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name=OPENAI_EMBED_MODEL,
        )

    # local fallback
    from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
    return OllamaEmbeddingFunction(
        url=f"{OLLAMA_URL}/api/embeddings",
        model_name=OLLAMA_EMBED_MODEL,
    )


def get_embed_model_name() -> str:
    """Return which model is currently active — for logging."""
    return OPENAI_EMBED_MODEL if os.getenv("OPENAI_API_KEY") else OLLAMA_EMBED_MODEL


# ── client ─────────────────────────────────────────────────────────────────────

def get_client() -> chromadb.Client:
    CHROMA_DIR.mkdir(exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


# ── test embedding connection ──────────────────────────────────────────────────

def test_embedding_fn(embed_fn) -> bool:
    model = get_embed_model_name()
    print(f"Testing embedding model: {model} …")
    try:
        result = embed_fn(["test connection"])
        if result and len(result[0]) > 0:
            print(f"  OK — dim: {len(result[0])}\n")
            return True
    except Exception as e:
        print(f"  FAILED: {e}")
        if "OPENAI" in model.upper() or "text-embedding" in model:
            print("  Check: OPENAI_API_KEY is set correctly")
        else:
            print("  Check: ollama serve  +  ollama pull nomic-embed-text")
        return False
    return False


# ── helpers ────────────────────────────────────────────────────────────────────

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


def build_metadata(chunk: dict) -> dict:
    return {
        "chunk_type":  chunk.get("chunk_type",  ""),
        "hts_code":    chunk.get("hts_code",    ""),
        "heading":     chunk.get("heading",     ""),
        "chapter":     chunk.get("chapter",     ""),
        "subheading":  chunk.get("subheading",  ""),
        "node_type":   chunk.get("node_type",   ""),
        "general_rate": chunk.get("general_rate", ""),
        "special_rate": chunk.get("special_rate", "")[:200],
        "other_rate":  chunk.get("other_rate",  ""),
        "unit_of_qty": chunk.get("unit_of_qty", ""),
        "hts_release": chunk.get("hts_release", ""),
        "doc_type":    chunk.get("doc_type",    "hts"),
        "token_est":   chunk.get("token_est",   0),
        "child_count": chunk.get("child_count", 0),
    }


def truncate_doc(text: str) -> str:
    if len(text) <= MAX_CHARS:
        return text
    truncated  = text[:MAX_CHARS]
    last_space = truncated.rfind(" ")
    return (truncated[:last_space] + " …") if last_space > MAX_CHARS * 0.8 else (truncated + " …")


# ── upsert ─────────────────────────────────────────────────────────────────────

def upsert_chunks(collection: chromadb.Collection, chunks: list[dict], label: str) -> None:
    total = len(chunks)
    done  = 0

    for i in range(0, total, BATCH_SIZE):
        batch     = chunks[i: i + BATCH_SIZE]
        ids       = [c["chunk_id"]               for c in batch]
        documents = [truncate_doc(c["chunk_text"]) for c in batch]
        metadatas = [build_metadata(c)             for c in batch]

        try:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            done += len(batch)
        except Exception as err:
            if "context length" in str(err).lower() or "input length" in str(err).lower():
                for cid, doc, meta in zip(ids, documents, metadatas):
                    safe = doc[:1000] if len(doc) > 1000 else doc
                    try:
                        collection.upsert(ids=[cid], documents=[safe], metadatas=[meta])
                        done += 1
                    except Exception as item_err:
                        print(f"\n  SKIP {cid}: {item_err}")
            else:
                raise

        pct = int(100 * done / total)
        print(f"\r  {label}: [{'='*int(pct/5):<20}] {pct:3d}%  {done:,}/{total:,}", end="", flush=True)

    print()


# ── build collection ────────────────────────────────────────────────────────────

def build_collection(client, embed_fn, name: str, chunks: list[dict]):
    try:
        client.delete_collection(name)
        print(f"  Cleared: {name}")
    except Exception:
        pass

    collection = client.create_collection(
        name=name,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )
    t0 = time.time()
    upsert_chunks(collection, chunks, name)
    elapsed = time.time() - t0
    count   = collection.count()
    print(f"  Indexed {count:,} chunks in {elapsed:.1f}s ({count/elapsed:.0f}/s)")
    return collection


# ── query ───────────────────────────────────────────────────────────────────────

def query_collection(
    collection: chromadb.Collection,
    query:      str,
    n:          int = 5,
    chapter:    str = "",
    node_type:  str = "",
) -> list[dict]:
    where: dict[str, Any] = {}
    if chapter and node_type:
        where = {"$and": [{"chapter": {"$eq": chapter}}, {"node_type": {"$eq": node_type}}]}
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
    return [
        {"document": doc, "metadata": meta, "score": round(1 - dist, 4)}
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


# ── interactive query ───────────────────────────────────────────────────────────

def run_query(query: str, chapter: str = "") -> None:
    client   = get_client()
    embed_fn = get_embedding_fn()
    print(f'\nQuery: "{query}"  (model: {get_embed_model_name()})')
    if chapter:
        print(f"Filter: chapter={chapter}")
    print()

    for col_name, label in [(COL_HEADINGS, "Heading"), (COL_NODES, "Node")]:
        try:
            col     = client.get_collection(col_name, embedding_function=embed_fn)
            results = query_collection(col, query, n=4, chapter=chapter)
            print(f"── {label} matches ──────────────────────────────────────────────")
            for r in results:
                m = r["metadata"]
                print(f"  [{r['score']:.3f}] {m.get('hts_code') or m.get('heading',''):<16} "
                      f"ch={m.get('chapter',''):<4} rate={m.get('general_rate') or '—'}")
                print(f"          {r['document'].split(chr(10))[0][:100]}")
            print()
        except Exception as e:
            print(f"  {col_name} not found: {e}\n")


# ── main ────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="Build / query HTS vector store")
    ap.add_argument("--query",           metavar="TEXT")
    ap.add_argument("--chapter",         metavar="CH",  default="")
    ap.add_argument("--collection",      choices=["nodes", "headings", "both"], default="both")
    ap.add_argument("--resume-headings", action="store_true")
    ap.add_argument("--skip-build",      action="store_true")
    args = ap.parse_args()

    if args.query and args.skip_build:
        run_query(args.query, chapter=args.chapter)
        return

    if not args.skip_build:
        embed_fn = get_embedding_fn()
        if not test_embedding_fn(embed_fn):
            sys.exit(1)

        client = get_client()

        build_nodes    = not args.resume_headings and args.collection in ("nodes", "both")
        build_headings = args.resume_headings     or args.collection in ("headings", "both")

        if build_nodes:
            chunks = load_jsonl(CHUNKS_NODE)
            print(f"Building {COL_NODES}  ({len(chunks):,} chunks)  model={get_embed_model_name()}\n")
            build_collection(client, embed_fn, COL_NODES, chunks)
            print()

        if build_headings:
            chunks = load_jsonl(CHUNKS_HEAD)
            print(f"Building {COL_HEADINGS}  ({len(chunks):,} chunks)  model={get_embed_model_name()}\n")
            build_collection(client, embed_fn, COL_HEADINGS, chunks)
            print()

        print(f"── Done  ({CHROMA_DIR}) ─────────────────────────────────────────")
        for name in [COL_NODES, COL_HEADINGS]:
            try:
                print(f"  {name:<20}: {client.get_collection(name).count():,} chunks")
            except Exception:
                pass

    if args.query:
        run_query(args.query, chapter=args.chapter)


if __name__ == "__main__":
    main()