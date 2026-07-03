"""Load and chunk durable memory markdown for vector retrieval."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ..memory_store import memory_dir, read_memory_file


def _chunk_id(rel_path: str, index: int) -> str:
    return hashlib.sha256(f"{rel_path}|{index}".encode()).hexdigest()[:16]


def chunk_markdown(
    rel_path: str,
    title: str,
    body: str,
    *,
    max_chars: int = 900,
    overlap: int = 120,
) -> list[dict[str, Any]]:
    """Simple paragraph-aware chunks (no tiktoken dep in the API server)."""
    text = body.strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[dict[str, Any]] = []
    buf = ""
    idx = 0
    for para in paragraphs:
        candidate = f"{buf}\n\n{para}".strip() if buf else para
        if len(candidate) <= max_chars:
            buf = candidate
            continue
        if buf:
            chunks.append(_make_chunk(rel_path, title, buf, idx))
            idx += 1
            tail = buf[-overlap:] if overlap and len(buf) > overlap else ""
            buf = f"{tail}\n\n{para}".strip() if tail else para
        else:
            for i in range(0, len(para), max_chars - overlap):
                piece = para[i : i + max_chars]
                chunks.append(_make_chunk(rel_path, title, piece, idx))
                idx += 1
            buf = ""
    if buf:
        chunks.append(_make_chunk(rel_path, title, buf, idx))
    return chunks


def _make_chunk(rel_path: str, title: str, text: str, index: int) -> dict[str, Any]:
    return {
        "chunk_id": _chunk_id(rel_path, index),
        "memory_key": rel_path,
        "title": title,
        "text": text,
        "path": rel_path,
    }


def list_memory_paths(session_id: str) -> list[tuple[str, str]]:
    """Return (rel_path, title) for session + global markdown files."""
    root = memory_dir()
    paths: list[tuple[str, str]] = []
    for folder_name in ("global", session_id.strip() or "global"):
        folder = root / folder_name
        if not folder.is_dir():
            continue
        for p in sorted(folder.glob("*.md")):
            rel = f"{folder_name}/{p.name}"
            title = p.stem
            try:
                first = p.read_text(encoding="utf-8").split("\n", 1)[0]
                if first.startswith("# "):
                    title = first[2:].strip() or title
            except OSError:
                continue
            paths.append((rel, title))
    return paths


def load_session_chunks(session_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rel, title in list_memory_paths(session_id):
        body = read_memory_file(rel)
        if not body:
            continue
        out.extend(chunk_markdown(rel, title, body))
    return out
