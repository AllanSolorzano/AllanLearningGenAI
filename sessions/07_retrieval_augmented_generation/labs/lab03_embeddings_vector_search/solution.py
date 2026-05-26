#!/usr/bin/env python3
"""Lab 03 — solution."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.rag_utils import (
    cosine_similarity,
    flatten_pages,
    heading_aware_chunks,
    merge_small_chunks,
    metadata_filter,
)
from shared.runbooks import DOCUMENTS


def build_chunks() -> list[dict]:
    out: list[dict] = []
    for doc in DOCUMENTS:
        for page in flatten_pages(doc):
            out.extend(heading_aware_chunks(page))
    return merge_small_chunks(out)


def search(
    query: str,
    chunks: list[dict],
    embeddings: np.ndarray,
    model: SentenceTransformer,
    *,
    filters: dict[str, str] | None = None,
    top_k: int = 3,
) -> list[tuple[dict, float]]:
    filtered = metadata_filter(chunks, filters or {})
    if not filtered:
        return []
    idx_map = [chunks.index(c) for c in filtered]
    sub_emb = embeddings[idx_map]
    q = model.encode([query])[0]
    sims = cosine_similarity(q, sub_emb)
    pairs = [(filtered[i], float(sims[i])) for i in range(len(filtered))]
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs[:top_k]


def main() -> None:
    chunks = build_chunks()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode([c["text"] for c in chunks])
    for q, flt in [("container killed for memory", {}), ("terraform lock", {"service": "terraform"})]:
        print(f"\nQuery: {q}")
        for ch, score in search(q, chunks, embeddings, model, filters=flt):
            print(f"  {score:.4f} [{ch['doc_id']}] {ch['heading']}")


if __name__ == "__main__":
    main()
