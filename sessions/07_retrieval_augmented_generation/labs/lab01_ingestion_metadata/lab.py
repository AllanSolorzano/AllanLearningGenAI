#!/usr/bin/env python3
"""
Lab 01: Ingestion and Metadata
==============================
Build page records with cleaning, metadata, and stable chunk IDs.

Run: python lab.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.runbooks import DOCUMENTS


def ingest_document(doc: dict) -> list[dict]:
    """Return cleaned page records with full metadata."""
    # TODO 1: import clean_text from shared.rag_utils
    # For each page in doc["pages"]:
    #   - clean text
    #   - build dict with doc_id, title, source, service, environment, owner, version, page, heading, text
    pass


def page_record_id(record: dict) -> str:
    """Stable ID for a page (not yet chunked)."""
    # TODO 2: hash doc_id + page + heading (use hashlib.sha256, hex[:16])
    pass


def main() -> None:
    print("Lab 01: Ingestion and Metadata\n")
    all_pages: list[dict] = []
    for doc in DOCUMENTS:
        pages = ingest_document(doc)
        if pages is None:
            print("Complete TODO 1")
            return
        all_pages.extend(pages)
        print(f"{doc['doc_id']}: {len(pages)} pages")

    print(f"\nTotal pages: {len(all_pages)}")
    sample = all_pages[0]
    pid = page_record_id(sample)
    if pid:
        print(f"Sample page ID: {pid}")
        print(f"  service={sample.get('service')} env={sample.get('environment')}")
        print(f"  heading={sample.get('heading')}")
        print(f"  text={sample.get('text', '')[:100]}...")


if __name__ == "__main__":
    main()
