#!/usr/bin/env python3
"""
Lab 05: Grounded Answers with Citations
=======================================
Full mini-RAG: retrieve, rerank, assemble context, cite, not-found.

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


def answer_with_citations(query: str, chunks: list[dict], model: SentenceTransformer) -> dict:
    # TODO 1: hybrid_retrieve_chunks (from shared.rag_utils) -> assemble_context,
    # format_citations, grounded_answer_stub
    pass


def main() -> None:
    model = SentenceTransformer("all-MiniLM-L6-v2")
    chunks = build_chunks()
    for query in [
        "how do I fix OOMKilled pods",
        "what is the capital of France",
    ]:
        print("=" * 60)
        print(f"Q: {query}")
        result = answer_with_citations(query, chunks, model)
        if not result:
            print("Complete TODO 1")
            continue
        print(f"found={result.get('found')}")
        print(result.get("answer", ""))
        for cite in result.get("citations") or []:
            print(f"  {cite}")


if __name__ == "__main__":
    main()
