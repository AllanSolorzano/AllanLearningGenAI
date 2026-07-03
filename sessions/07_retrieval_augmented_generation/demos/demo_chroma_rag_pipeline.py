#!/usr/bin/env python3
"""
Optional demo: full local RAG with ChromaDB + sentence-transformers.

Requires: pip install chromadb sentence-transformers

Usage:
    python demo_chroma_rag_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shared.rag_utils import (
    assemble_context,
    flatten_pages,
    format_citations,
    grounded_answer_stub,
    heading_aware_chunks,
    merge_small_chunks,
    rerank_by_overlap,
)
from shared.runbooks import DOCUMENTS


def main() -> None:
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        print("Missing dependency:", e)
        print("Install: pip install chromadb sentence-transformers")
        sys.exit(1)

    chunks: list[dict] = []
    for doc in DOCUMENTS:
        for page in flatten_pages(doc):
            chunks.extend(heading_aware_chunks(page))
    chunks = merge_small_chunks(chunks)

    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.Client()
    collection = client.create_collection("runbooks_v1")

    ids = [c["chunk_id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "doc_id": c["doc_id"],
            "heading": c.get("heading", ""),
            "page": c.get("page", 0),
            "service": c.get("service", ""),
        }
        for c in chunks
    ]
    embeddings = model.encode(documents).tolist()
    collection.add(ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings)

    query = "nginx returns bad gateway to users"
    print(f"Query: {query}\n")

    q_emb = model.encode([query]).tolist()
    results = collection.query(query_embeddings=q_emb, n_results=10)
    hit_ids = results["ids"][0]
    hit_docs = results["documents"][0]
    hit_meta = results["metadatas"][0]
    distances = results["distances"][0]

    candidates: list[dict] = []
    for i, cid in enumerate(hit_ids):
        candidates.append(
            {
                "chunk_id": cid,
                "text": hit_docs[i],
                "doc_id": hit_meta[i].get("doc_id"),
                "heading": hit_meta[i].get("heading"),
                "page": hit_meta[i].get("page"),
                "source": "chroma",
                "_retrieval_score": 1.0 - float(distances[i]),
            }
        )

    top = rerank_by_overlap(query, candidates, top_k=5)
    print("Context:\n", assemble_context(top))
    print("\nCitations:", format_citations(top))
    answer = grounded_answer_stub(query, top)
    print("\nGrounded answer:\n", answer["answer"])


if __name__ == "__main__":
    main()
