#!/usr/bin/env python3
"""Lab 04 — solution."""

from __future__ import annotations

import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.rag_utils import (
    flatten_pages,
    heading_aware_chunks,
    hybrid_retrieve_chunks,
    merge_small_chunks,
)
from shared.runbooks import DOCUMENTS


def build_chunks() -> list[dict]:
    out: list[dict] = []
    for doc in DOCUMENTS:
        for page in flatten_pages(doc):
            out.extend(heading_aware_chunks(page))
    return merge_small_chunks(out)


def hybrid_retrieve(
    query: str,
    chunks: list[dict],
    model: SentenceTransformer,
    *,
    top_n: int = 10,
    rerank_k: int = 5,
) -> list[dict]:
    embeddings = model.encode([c["text"] for c in chunks])
    return hybrid_retrieve_chunks(
        query, chunks, embeddings, model, top_n=top_n, rerank_k=rerank_k
    )


def main() -> None:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    chunks = build_chunks()
    for ch in hybrid_retrieve("502 bad gateway from ingress", chunks, model):
        print(f"[{ch['doc_id']}] {ch['heading']}")


if __name__ == "__main__":
    main()
