#!/usr/bin/env python3
"""Demo: vector, keyword, hybrid (RRF), and reranking over the runbook corpus."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.rag_utils import (
    flatten_pages,
    heading_aware_chunks,
    keyword_rank,
    merge_small_chunks,
    reciprocal_rank_fusion,
    rerank_by_overlap,
    vector_rank,
)
from shared.runbooks import DOCUMENTS


def build_chunks() -> list[dict]:
    chunks: list[dict] = []
    for doc in DOCUMENTS:
        for page in flatten_pages(doc):
            chunks.extend(heading_aware_chunks(page))
    return merge_small_chunks(chunks)


def print_hits(title: str, ranked: list[tuple[str, float]], by_id: dict[str, dict]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    for cid, score in ranked[:5]:
        ch = by_id[cid]
        print(f"  {score:.4f}  [{ch['doc_id']}] {ch['heading']} — {ch['text'][:70]}...")


def main() -> None:
    chunks = build_chunks()
    by_id = {c["chunk_id"]: c for c in chunks}
    texts = [c["text"] for c in chunks]

    print("Loading embedding model (~80MB first run)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(texts)

    queries = [
        "pod keeps restarting and crashing",
        "database connections exhausted",
        "terraform state locked",
    ]

    for query in queries:
        print("\n" + "=" * 72)
        print(f"Query: {query}")

        vec = vector_rank(query, chunks, embeddings, model, top_n=10)
        kw = keyword_rank(query, chunks, top_n=10)
        fused = reciprocal_rank_fusion(
            [[cid for cid, _ in vec], [cid for cid, _ in kw]],
            top_n=10,
        )

        print_hits("Vector top 5", vec, by_id)
        print_hits("BM25 top 5", kw, by_id)
        print_hits("RRF hybrid top 5", fused, by_id)

        candidates = []
        for cid, score in fused[:10]:
            ch = dict(by_id[cid])
            ch["_retrieval_score"] = score
            candidates.append(ch)
        reranked = rerank_by_overlap(query, candidates, top_k=3)
        print("\nReranked top 3")
        for ch in reranked:
            print(f"  [{ch['doc_id']}] {ch['heading']}")


if __name__ == "__main__":
    main()
