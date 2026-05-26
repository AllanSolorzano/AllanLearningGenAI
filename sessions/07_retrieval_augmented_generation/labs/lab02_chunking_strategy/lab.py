#!/usr/bin/env python3
"""
Lab 02: Chunking Strategy
=========================
Heading-aware token chunks, overlap, and merge-small.

Run: python lab.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.rag_utils import flatten_pages
from shared.runbooks import DOCUMENTS


def chunk_corpus(
    *,
    max_tokens: int = 120,
    overlap_tokens: int = 20,
    min_merge_tokens: int = 40,
) -> list[dict]:
    """Chunk all documents in DOCUMENTS."""
    # TODO 1: for each doc, flatten_pages, heading_aware_chunks per page, merge_small_chunks
    pass


def main() -> None:
    print("Lab 02: Chunking Strategy\n")
    chunks = chunk_corpus()
    if not chunks:
        print("Complete TODO 1")
        return
    print(f"Total chunks: {len(chunks)}")
    by_doc: dict[str, int] = {}
    for c in chunks:
        by_doc[c["doc_id"]] = by_doc.get(c["doc_id"], 0) + 1
    for doc_id, n in sorted(by_doc.items()):
        print(f"  {doc_id}: {n} chunks")
    longest = max(chunks, key=lambda x: x.get("token_count", 0))
    print(f"\nLongest chunk: {longest['token_count']} tokens — {longest['heading']}")


if __name__ == "__main__":
    main()
