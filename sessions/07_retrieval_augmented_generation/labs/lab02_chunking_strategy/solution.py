#!/usr/bin/env python3
"""Lab 02 — solution."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.rag_utils import flatten_pages, heading_aware_chunks, merge_small_chunks
from shared.runbooks import DOCUMENTS


def chunk_corpus(
    *,
    max_tokens: int = 120,
    overlap_tokens: int = 20,
    min_merge_tokens: int = 40,
) -> list[dict]:
    chunks: list[dict] = []
    for doc in DOCUMENTS:
        for page in flatten_pages(doc):
            chunks.extend(
                heading_aware_chunks(
                    page, max_tokens=max_tokens, overlap_tokens=overlap_tokens
                )
            )
    return merge_small_chunks(chunks, min_tokens=min_merge_tokens)


def main() -> None:
    chunks = chunk_corpus()
    print(f"Total chunks: {len(chunks)}")


if __name__ == "__main__":
    main()
