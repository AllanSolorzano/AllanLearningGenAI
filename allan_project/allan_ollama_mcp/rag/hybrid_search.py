"""Hybrid BM25 + vector search over memory chunks; fused with FTS in kb_connector."""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from functools import lru_cache
from typing import Any

from .memory_chunks import load_session_chunks

_CHUNK_CACHE: dict[str, list[dict[str, Any]]] = {}


def hybrid_enabled() -> bool:
    return os.environ.get("ALLAN_RAG_HYBRID", "").strip().lower() in ("1", "true", "yes")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_.-]{0,48}", text.lower())


def _bm25(query: str, corpus: list[str]) -> list[float]:
    docs = [_tokenize(t) for t in corpus]
    q = _tokenize(query)
    if not docs or not q:
        return [0.0] * len(corpus)
    N, avgdl = len(docs), sum(len(d) for d in docs) / len(docs)
    df: Counter[str] = Counter()
    for d in docs:
        for t in set(d):
            df[t] += 1
    k1, b = 1.5, 0.75
    scores: list[float] = []
    for d in docs:
        tf = Counter(d)
        dl = len(d)
        s = 0.0
        for term in q:
            if term not in tf:
                continue
            n = df.get(term, 0)
            idf = math.log((N - n + 0.5) / (n + 0.5) + 1.0)
            freq = tf[term]
            denom = freq + k1 * (1 - b + b * dl / avgdl)
            s += idf * (freq * (k1 + 1)) / denom
        scores.append(s)
    return scores


def _rrf(rank_lists: list[list[str]], *, k: int = 60, top_n: int = 12) -> list[str]:
    scores: dict[str, float] = {}
    for lst in rank_lists:
        for rank, key in enumerate(lst, start=1):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [key for key, _ in ordered[:top_n]]


@lru_cache(maxsize=1)
def _embedding_model() -> Any:
    from sentence_transformers import SentenceTransformer

    name = os.environ.get("ALLAN_RAG_EMBED_MODEL", "all-MiniLM-L6-v2")
    return SentenceTransformer(name)


def _chunks_for_session(session_id: str) -> list[dict[str, Any]]:
    sid = session_id.strip() or "global"
    if sid not in _CHUNK_CACHE:
        _CHUNK_CACHE[sid] = load_session_chunks(sid)
    return _CHUNK_CACHE[sid]


def invalidate_chunk_cache(session_id: str | None = None) -> None:
    if session_id:
        _CHUNK_CACHE.pop(session_id.strip() or "global", None)
    else:
        _CHUNK_CACHE.clear()


async def hybrid_memory_search(
    session_id: str,
    query_text: str,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """
    Vector + BM25 + RRF over chunked durable memory.

    Returns chunk dicts compatible with kb_connector (memory_id/path/title/snippet).
    """
    if not hybrid_enabled():
        return []

    chunks = _chunks_for_session(session_id)
    if not chunks:
        return []

    import numpy as np

    model = _embedding_model()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts)
    q = model.encode([query_text])[0]
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    em = embeddings / norms
    qn = q / (np.linalg.norm(q) or 1.0)
    vec_scores = (em @ qn).tolist()

    bm25 = _bm25(query_text, texts)
    vec_ranked = sorted(
        range(len(chunks)),
        key=lambda i: vec_scores[i],
        reverse=True,
    )[:20]
    kw_ranked = sorted(range(len(chunks)), key=lambda i: bm25[i], reverse=True)[:20]
    fused_ids = _rrf(
        [
            [chunks[i]["chunk_id"] for i in vec_ranked],
            [chunks[i]["chunk_id"] for i in kw_ranked],
        ],
        top_n=limit,
    )
    by_id = {c["chunk_id"]: c for c in chunks}
    out: list[dict[str, Any]] = []
    for cid in fused_ids:
        ch = by_id.get(cid)
        if not ch:
            continue
        out.append(
            {
                "memory_id": ch["chunk_id"],
                "path": ch["path"],
                "title": ch.get("title") or "",
                "snippet": ch["text"][:400],
                "scope": "rag_hybrid",
                "source": "rag_hybrid",
            }
        )
    return out
