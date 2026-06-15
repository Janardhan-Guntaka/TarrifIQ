"""Build legal note chunks for embedding (100–500 token target)."""

import json
import pathlib
from typing import Any


def est_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def load_general_notes(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    notes = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                notes.append(json.loads(line))
    return notes


def chunk_legal_notes(
    notes: list[dict[str, Any]],
    *,
    max_chars: int = 2000,
) -> list[dict[str, Any]]:
    """
    One chunk per note row; split long notes by paragraph if needed.
    """
    chunks: list[dict[str, Any]] = []
    for i, note in enumerate(notes):
        text = note.get("chunk_text") or note.get("description", "")
        if not text:
            continue

        parts = [text] if len(text) <= max_chars else _split_text(text, max_chars)

        for j, part in enumerate(parts):
            chunk_id = f"legal_{i}_{j}"
            chunks.append({
                "chunk_id": chunk_id,
                "chunk_text": part.strip(),
                "doc_type": "legal_note",
                "hts_code": "",
                "metadata": {
                    "note_type": "general",
                    "chapter": note.get("chapter", ""),
                    "indent": note.get("indent"),
                    "hts_release": note.get("hts_release", ""),
                },
                "token_est": est_tokens(part),
            })
    return chunks


def _split_text(text: str, max_chars: int) -> list[str]:
    paragraphs = text.split(". ")
    parts: list[str] = []
    current = ""
    for p in paragraphs:
        segment = p if p.endswith(".") else p + ". "
        if len(current) + len(segment) <= max_chars:
            current += segment
        else:
            if current:
                parts.append(current.strip())
            current = segment
    if current:
        parts.append(current.strip())
    return parts or [text[:max_chars]]
