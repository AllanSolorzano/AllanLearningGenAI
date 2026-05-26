#!/usr/bin/env python3
"""Lab 01 — solution."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from shared.rag_utils import clean_text
from shared.runbooks import DOCUMENTS


def ingest_document(doc: dict) -> list[dict]:
    records: list[dict] = []
    for page in doc.get("pages") or []:
        body = clean_text(str(page.get("text") or ""))
        if not body:
            continue
        records.append(
            {
                "doc_id": doc["doc_id"],
                "title": doc.get("title", ""),
                "source": doc.get("source", ""),
                "service": doc.get("service", ""),
                "environment": doc.get("environment", ""),
                "owner": doc.get("owner", ""),
                "version": doc.get("version", ""),
                "page": int(page.get("page") or 0),
                "heading": clean_text(str(page.get("heading") or "")),
                "text": body,
            }
        )
    return records


def page_record_id(record: dict) -> str:
    raw = f"{record['doc_id']}|{record['page']}|{record.get('heading', '')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def main() -> None:
    print("Lab 01: Ingestion and Metadata (solution)\n")
    all_pages: list[dict] = []
    for doc in DOCUMENTS:
        pages = ingest_document(doc)
        all_pages.extend(pages)
        print(f"{doc['doc_id']}: {len(pages)} pages")
    print(f"\nTotal pages: {len(all_pages)}")
    sample = all_pages[0]
    print(f"Sample page ID: {page_record_id(sample)}")


if __name__ == "__main__":
    main()
