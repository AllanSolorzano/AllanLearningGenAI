#!/usr/bin/env python3
"""
Lab 03: Embeddings and Vector Search
====================================
Embed chunks, cosine search, metadata filters.

Run: python lab.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.rag_utils import flatten_pages, heading_aware_chunks, merge_small_chunks
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
    # TODO 1: metadata_filter, embed query, cosine_similarity, return top_k (chunk, score)
    pass


def main() -> None:
    chunks = build_chunks()
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode([c["text"] for c in chunks])

    queries = [
        ("container killed for memory", {}),
        ("terraform lock", {"service": "terraform"}),
    ]
    for q, flt in queries:
        print(f"\nQuery: {q}  filters={flt}")
        hits = search(q, chunks, embeddings, model, filters=flt, top_k=3)
        if not hits:
            print("  Complete TODO 1")
            continue
        for ch, score in hits:
            print(f"  {score:.4f} [{ch['doc_id']}] {ch['heading']}")


if __name__ == "__main__":
    main()
