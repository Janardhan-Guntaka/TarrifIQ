"""
startup.py
----------
Auto-builds ChromaDB collections if they don't exist.
Called at the top of ui/app.py before anything else.

On Streamlit Cloud:
  - First run: builds both collections from data/processed/chunks/
    using OpenAI embeddings. Takes ~15 min, costs ~$0.04.
  - Subsequent runs: collections already exist, skips build (~1s check).

On local dev:
  - If .chroma/ exists: skips build.
  - If .chroma/ missing: builds with whichever embedding is configured.
"""

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHROMA_DIR  = ROOT / ".chroma"
CHUNKS_NODE = ROOT / "data/processed/chunks/chunks_node.jsonl"
CHUNKS_HEAD = ROOT / "data/processed/chunks/chunks_heading.jsonl"


def collections_exist() -> bool:
    """Check if both collections are already built."""
    if not CHROMA_DIR.exists():
        return False
    try:
        import chromadb
        from stores.vector_store import get_client, get_embedding_fn, COL_NODES, COL_HEADINGS
        client = get_client()
        embed_fn = get_embedding_fn()
        n = client.get_collection(COL_NODES,    embedding_function=embed_fn).count()
        h = client.get_collection(COL_HEADINGS, embedding_function=embed_fn).count()
        return n > 1000 and h > 100
    except Exception:
        return False


def build_collections() -> None:
    """Build both ChromaDB collections from processed chunks."""
    from stores.vector_store import (
        get_client, get_embedding_fn, get_embed_model_name,
        load_jsonl, build_collection,
        COL_NODES, COL_HEADINGS, CHUNKS_NODE, CHUNKS_HEAD,
    )

    if not CHUNKS_NODE.exists() or not CHUNKS_HEAD.exists():
        print("ERROR: Chunk files not found. Run ingestion/chunker.py first.")
        return

    print(f"Building ChromaDB collections (model: {get_embed_model_name()})...")
    print("This runs once and takes ~15 minutes on first deploy.")

    client   = get_client()
    embed_fn = get_embedding_fn()

    node_chunks = load_jsonl(CHUNKS_NODE)
    print(f"  Building {COL_NODES} ({len(node_chunks):,} chunks)...")
    build_collection(client, embed_fn, COL_NODES, node_chunks)

    head_chunks = load_jsonl(CHUNKS_HEAD)
    print(f"  Building {COL_HEADINGS} ({len(head_chunks):,} chunks)...")
    build_collection(client, embed_fn, COL_HEADINGS, head_chunks)

    print("ChromaDB build complete.")


def ensure_vector_store() -> None:
    """
    Main entry point. Call this at app startup.
    Builds collections if missing, skips if already built.
    """
    if collections_exist():
        return  # already built, nothing to do

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("WARNING: OPENAI_API_KEY not set. Vector store cannot be built.")
        print("  Set the key in Streamlit secrets and reboot the app.")
        return

    build_collections()