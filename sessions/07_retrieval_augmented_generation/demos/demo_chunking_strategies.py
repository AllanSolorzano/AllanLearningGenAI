#!/usr/bin/env python3
"""Demo: how chunk size, overlap, and headings affect retrieval-ready text."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.rag_utils import count_tokens, flatten_pages, heading_aware_chunks, merge_small_chunks
from shared.runbooks import DOCUMENTS


def main() -> None:
    doc = DOCUMENTS[0]
    pages = flatten_pages(doc)
    print(f"Document: {doc['doc_id']} — {doc['title']}")
    print(f"Pages after ingest/clean: {len(pages)}\n")

    strategies = [
        ("small chunks (60 tok)", 60, 10),
        ("default (120 tok)", 120, 20),
        ("large chunks (200 tok)", 200, 30),
    ]
    for label, max_tok, overlap in strategies:
        chunks: list[dict] = []
        for page in pages:
            chunks.extend(
                heading_aware_chunks(page, max_tokens=max_tok, overlap_tokens=overlap)
            )
        merged = merge_small_chunks(chunks)
        avg = sum(c["token_count"] for c in merged) / max(len(merged), 1)
        print(f"{label:22} -> {len(merged)} chunks, avg {avg:.0f} tokens")
        sample = merged[0]["text"][:120].replace("\n", " ")
        print(f"  sample: {sample}...\n")

    page = pages[1]
    ch = heading_aware_chunks(page, max_tokens=40, overlap_tokens=8)
    print("Overlap demo (max 40 tokens):")
    for i, c in enumerate(ch):
        print(f"  chunk {i}: {count_tokens(c['text'])} tokens — {c['text'][:80]}...")


if __name__ == "__main__":
    main()
