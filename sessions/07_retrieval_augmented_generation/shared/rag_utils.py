"""Reusable RAG helpers for Session 07 labs, demos, and allan_project."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Any

import numpy as np

try:
    import tiktoken
except ImportError:  # pragma: no cover
    tiktoken = None  # type: ignore


def clean_text(text: str) -> str:
    """Normalize whitespace and strip control characters while keeping meaning."""
    text = text.replace("\x00", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def stable_chunk_id(doc_id: str, page: int, heading: str, chunk_index: int) -> str:
    raw = f"{doc_id}|{page}|{heading}|{chunk_index}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def flatten_pages(doc: dict) -> list[dict]:
    """Turn a document with pages into cleaned page records with metadata."""
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


def _encoding():
    if tiktoken is None:
        raise RuntimeError("tiktoken is required for token-aware chunking")
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    enc = _encoding()
    return len(enc.encode(text))


def heading_aware_chunks(
    page: dict,
    *,
    max_tokens: int = 120,
    overlap_tokens: int = 20,
) -> list[dict]:
    """Split a page into heading-prefixed token chunks with overlap."""
    enc = _encoding()
    heading = page.get("heading") or ""
    prefix = f"## {heading}\n\n" if heading else ""
    body = page.get("text") or ""
    full = prefix + body
    token_ids = enc.encode(full)
    if len(token_ids) <= max_tokens:
        return [
            {
                "chunk_id": stable_chunk_id(page["doc_id"], page["page"], heading, 0),
                "text": full,
                "token_count": len(token_ids),
                **{k: page[k] for k in ("doc_id", "title", "source", "service", "environment", "owner", "version", "page", "heading")},
            }
        ]

    chunks: list[dict] = []
    start = 0
    idx = 0
    while start < len(token_ids):
        end = min(start + max_tokens, len(token_ids))
        piece = enc.decode(token_ids[start:end])
        chunks.append(
            {
                "chunk_id": stable_chunk_id(page["doc_id"], page["page"], heading, idx),
                "text": piece,
                "token_count": end - start,
                **{k: page[k] for k in ("doc_id", "title", "source", "service", "environment", "owner", "version", "page", "heading")},
            }
        )
        if end >= len(token_ids):
            break
        start = max(0, end - overlap_tokens)
        idx += 1
    return chunks


def merge_small_chunks(chunks: list[dict], *, min_tokens: int = 40) -> list[dict]:
    """Merge consecutive tiny chunks on the same page to reduce fragmentation."""
    if not chunks:
        return []
    merged: list[dict] = []
    buf: dict | None = None
    for ch in chunks:
        if buf is None:
            buf = dict(ch)
            continue
        same_page = buf.get("doc_id") == ch.get("doc_id") and buf.get("page") == ch.get("page")
        if same_page and buf.get("token_count", 0) < min_tokens:
            buf["text"] = f"{buf['text']}\n{ch['text']}".strip()
            buf["token_count"] = count_tokens(buf["text"])
            buf["chunk_id"] = stable_chunk_id(
                buf["doc_id"], buf["page"], buf.get("heading", ""), 0
            )
        else:
            merged.append(buf)
            buf = dict(ch)
    if buf:
        merged.append(buf)
    return merged


def normalize_rows(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vectors / norms


def cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    q = query_vec / (np.linalg.norm(query_vec) or 1.0)
    m = normalize_rows(matrix)
    return m @ q


def _tokenize_for_bm25(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_.-]{0,48}", text.lower())


def bm25_scores(query: str, corpus: list[str], *, k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Okapi BM25 over tokenized corpus (educational, no external deps)."""
    docs = [_tokenize_for_bm25(t) for t in corpus]
    query_tokens = _tokenize_for_bm25(query)
    if not docs or not query_tokens:
        return [0.0] * len(corpus)
    N = len(docs)
    avgdl = sum(len(d) for d in docs) / N
    df: Counter[str] = Counter()
    for d in docs:
        for term in set(d):
            df[term] += 1
    scores: list[float] = []
    for d in docs:
        dl = len(d)
        tf = Counter(d)
        score = 0.0
        for term in query_tokens:
            if term not in tf:
                continue
            n = df.get(term, 0)
            idf = math.log((N - n + 0.5) / (n + 0.5) + 1.0)
            freq = tf[term]
            denom = freq + k1 * (1 - b + b * dl / avgdl)
            score += idf * (freq * (k1 + 1)) / denom
        scores.append(score)
    return scores


def reciprocal_rank_fusion(
    ranked_lists: list[list[str]],
    *,
    k: int = 60,
    top_n: int = 20,
) -> list[tuple[str, float]]:
    """Fuse multiple ranked chunk_id lists with RRF."""
    scores: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, chunk_id in enumerate(lst, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return ordered[:top_n]


def keyword_rank(query: str, chunks: list[dict], *, top_n: int = 20) -> list[tuple[str, float]]:
    texts = [c["text"] for c in chunks]
    scores = bm25_scores(query, texts)
    pairs = [(chunks[i]["chunk_id"], scores[i]) for i in range(len(chunks))]
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs[:top_n]


def vector_rank(
    query: str,
    chunks: list[dict],
    embeddings: np.ndarray,
    model: Any,
    *,
    top_n: int = 20,
) -> list[tuple[str, float]]:
    q = model.encode([query])[0]
    sims = cosine_similarity(q, embeddings)
    pairs = [(chunks[i]["chunk_id"], float(sims[i])) for i in range(len(chunks))]
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs[:top_n]


def rerank_by_overlap(
    query: str,
    candidates: list[dict],
    *,
    top_k: int = 5,
) -> list[dict]:
    """Lightweight reranker: vector order + query token overlap (lab stand-in for cross-encoder)."""
    q_tokens = set(_tokenize_for_bm25(query))

    def score(ch: dict) -> float:
        t = set(_tokenize_for_bm25(ch.get("text", "")))
        overlap = len(q_tokens & t)
        base = float(ch.get("_retrieval_score", 0.0))
        return base + 0.05 * overlap

    ranked = sorted(candidates, key=score, reverse=True)
    return ranked[:top_k]


def metadata_filter(chunks: list[dict], filters: dict[str, str]) -> list[dict]:
    if not filters:
        return chunks
    out: list[dict] = []
    for ch in chunks:
        if all(str(ch.get(k, "")) == str(v) for k, v in filters.items()):
            out.append(ch)
    return out


def assemble_context(chunks: list[dict], *, max_chars: int = 6000) -> str:
    parts: list[str] = []
    used = 0
    for i, ch in enumerate(chunks, start=1):
        cite = f"[{i}] {ch.get('doc_id')} p{ch.get('page')} — {ch.get('heading', '')}"
        block = f"{cite}\n{ch.get('text', '')}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts).strip()


def format_citations(chunks: list[dict]) -> list[str]:
    cites: list[str] = []
    for i, ch in enumerate(chunks, start=1):
        cites.append(
            f"[{i}] {ch.get('doc_id')} ({ch.get('source')}) "
            f"page {ch.get('page')} — {ch.get('heading', 'section')}"
        )
    return cites


def hybrid_retrieve_chunks(
    query: str,
    chunks: list[dict],
    embeddings: np.ndarray,
    model: Any,
    *,
    top_n: int = 10,
    rerank_k: int = 5,
) -> list[dict]:
    """Vector + BM25 + RRF + overlap rerank."""
    vec = vector_rank(query, chunks, embeddings, model, top_n=top_n)
    kw = keyword_rank(query, chunks, top_n=top_n)
    fused = reciprocal_rank_fusion(
        [[cid for cid, _ in vec], [cid for cid, _ in kw]],
        top_n=top_n,
    )
    by_id = {c["chunk_id"]: c for c in chunks}
    candidates = []
    for cid, score in fused:
        ch = dict(by_id[cid])
        ch["_retrieval_score"] = score
        candidates.append(ch)
    return rerank_by_overlap(query, candidates, top_k=rerank_k)


def grounded_answer_stub(
    query: str,
    chunks: list[dict],
    *,
    min_score: float = 0.25,
) -> dict[str, Any]:
    """Template grounded answer without calling an LLM (labs work offline)."""
    if not chunks:
        return {
            "answer": "I could not find relevant runbook evidence for that question.",
            "found": False,
            "citations": [],
        }
    best = float(chunks[0].get("_retrieval_score", 0.0))
    if best < min_score:
        return {
            "answer": (
                "No sufficiently relevant passages were retrieved. "
                "Try rephrasing or narrowing filters (service, environment)."
            ),
            "found": False,
            "citations": [],
        }
    context = assemble_context(chunks)
    cites = format_citations(chunks)
    answer = (
        f"Based on indexed runbooks, here is a grounded summary for: {query}\n\n"
        f"{chunks[0].get('text', '')[:400]}\n\n"
        f"See citations: {'; '.join(cites)}"
    )
    return {"answer": answer, "found": True, "citations": cites, "context": context}
