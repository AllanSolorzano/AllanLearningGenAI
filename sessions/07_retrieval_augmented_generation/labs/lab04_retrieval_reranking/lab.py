#!/usr/bin/env python3
"""
Lab 04: Hybrid Retrieval and Reranking
======================================
BM25 + vector + RRF + lightweight rerank.

Run: python lab.py
"""

from __future__ import annotations

import sys
from pathlib import Path

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


def hybrid_retrieve(
    query: str,
    chunks: list[dict],
    model: SentenceTransformer,
    *,
    top_n: int = 10,
    rerank_k: int = 5,
) -> list[dict]:
    """Return reranked chunks with _retrieval_score set."""
    # TODO 1: vector_rank + keyword_rank + reciprocal_rank_fusion + rerank_by_overlap
    pass


def main() -> None:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    chunks = build_chunks()
    query = "502 bad gateway from ingress"
    print(f"Query: {query}\n")
    results = hybrid_retrieve(query, chunks, model)
    if not results:
        print("Complete TODO 1")
        return
    for ch in results:
        print(f"  [{ch['doc_id']}] {ch['heading']} (score={ch.get('_retrieval_score', 0):.4f})")


if __name__ == "__main__":
    main()
