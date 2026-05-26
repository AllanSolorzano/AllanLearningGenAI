#!/usr/bin/env python3
"""Lab 05 — solution."""

from __future__ import annotations

import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.rag_utils import (
    assemble_context,
    flatten_pages,
    format_citations,
    grounded_answer_stub,
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


def answer_with_citations(query: str, chunks: list[dict], model: SentenceTransformer) -> dict:
    embeddings = model.encode([c["text"] for c in chunks])
    top = hybrid_retrieve_chunks(query, chunks, embeddings, model, top_n=15, rerank_k=5)
    ctx = assemble_context(top)
    cites = format_citations(top)
    out = grounded_answer_stub(query, top, min_score=0.01)
    out["context"] = ctx
    out["citations"] = cites
    return out


def main() -> None:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    chunks = build_chunks()
    for query in ["how do I fix OOMKilled pods", "what is the capital of France"]:
        r = answer_with_citations(query, chunks, model)
        print(f"\nQ: {query}\nfound={r['found']}\n{r['answer'][:300]}...")


if __name__ == "__main__":
    main()
