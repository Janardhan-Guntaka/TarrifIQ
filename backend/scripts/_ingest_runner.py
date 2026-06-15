"""Shared ingestion logic for local CLI and future GitHub Actions."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from typing import Any
from uuid import UUID

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROCESSED_NODES = ROOT / "data/processed/hts/hts_nodes.jsonl"
PROCESSED_NOTES = ROOT / "data/processed/hts/general_notes.jsonl"
CHUNKS_NODE = ROOT / "data/processed/chunks/chunks_node.jsonl"
CHUNKS_HEAD = ROOT / "data/processed/chunks/chunks_heading.jsonl"


def _load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run_ingestion(
    *,
    version: str,
    raw_file: pathlib.Path | None,
    skip_parse: bool,
    activate: bool,
    embed: bool,
) -> UUID:
    from backend.core.deps import get_deps
    from backend.ingestion.hierarchy import assign_parent_codes, nodes_to_db_rows
    from backend.ingestion.legal_notes import chunk_legal_notes, load_general_notes

    deps = get_deps()
    existing = deps.releases.get_by_version(version)
    if existing:
        release_id = existing["id"]
        print(f"Using existing release row: {version} ({release_id})")
    else:
        release_id = deps.releases.create(version, status="processing")
        print(f"Created release: {version} ({release_id})")

    run_id = deps.releases.create_ingestion_run(release_id)

    try:
        if raw_file and not skip_parse:
            print(f"Parsing {raw_file} …")
            subprocess.check_call(
                [sys.executable, str(ROOT / "ingestion/parse_hts.py"), "--file", str(raw_file), "--release", version],
                cwd=str(ROOT),
            )

        if not PROCESSED_NODES.exists():
            raise FileNotFoundError(
                f"{PROCESSED_NODES} not found. Run parse_hts first or pass --file."
            )

        print("Loading hts_nodes …")
        nodes = _load_jsonl(PROCESSED_NODES)
        nodes = assign_parent_codes(nodes)
        db_rows = nodes_to_db_rows(nodes)
        count = deps.hts_nodes.bulk_insert(release_id, db_rows)
        print(f"  Inserted {count:,} hts_nodes")

        if embed:
            print("Chunking …")
            if not CHUNKS_NODE.exists():
                subprocess.check_call(
                    [sys.executable, str(ROOT / "ingestion/chunker.py")],
                    cwd=str(ROOT),
                )

            embed_svc = deps.embedding_service
            vector = deps.vector

            all_embed_records: list[dict[str, Any]] = []

            for label, path, doc_type in [
                ("nodes", CHUNKS_NODE, "node"),
                ("headings", CHUNKS_HEAD, "heading_summary"),
            ]:
                if not path.exists():
                    print(f"  Skip {label}: {path} missing")
                    continue
                chunks = _load_jsonl(path)
                print(f"  Embedding {len(chunks):,} {label} chunks …")
                texts = [c["chunk_text"][:2000] for c in chunks]
                vectors = embed_svc.embed_batch(texts)

                for c, vec in zip(chunks, vectors):
                    meta = {
                        "chapter": c.get("chapter", ""),
                        "heading": c.get("heading", ""),
                        "hts_code": c.get("hts_code", ""),
                        "node_type": c.get("node_type", ""),
                        "chunk_type": c.get("chunk_type", ""),
                    }
                    all_embed_records.append({
                        "chunk_id": c["chunk_id"],
                        "hts_code": c.get("hts_code") or None,
                        "doc_type": doc_type,
                        "chunk_text": c["chunk_text"][:2000],
                        "embedding": vec,
                        "metadata": json.dumps(meta),
                    })

            if PROCESSED_NOTES.exists():
                notes = load_general_notes(PROCESSED_NOTES)
                legal_chunks = chunk_legal_notes(notes)
                if legal_chunks:
                    print(f"  Embedding {len(legal_chunks):,} legal note chunks …")
                    texts = [c["chunk_text"] for c in legal_chunks]
                    vectors = embed_svc.embed_batch(texts)
                    for c, vec in zip(legal_chunks, vectors):
                        all_embed_records.append({
                            "chunk_id": c["chunk_id"],
                            "hts_code": None,
                            "doc_type": "legal_note",
                            "chunk_text": c["chunk_text"],
                            "embedding": vec,
                            "metadata": json.dumps(c.get("metadata", {})),
                        })

            print(f"  Upserting {len(all_embed_records):,} embeddings …")
            vector.bulk_insert_embeddings(release_id, all_embed_records)
            print(f"  Total embeddings: {vector.count_for_release(release_id):,}")

        if activate:
            deps.releases.activate(release_id)
            print(f"Activated release: {version}")

        deps.releases.update_ingestion_run(run_id, status="completed", step="done")
        print("Ingestion completed.")
        return release_id

    except Exception as e:
        deps.releases.update_ingestion_run(
            run_id, status="failed", step="error", error_message=str(e)
        )
        deps.releases.mark_failed(release_id, str(e))
        raise
