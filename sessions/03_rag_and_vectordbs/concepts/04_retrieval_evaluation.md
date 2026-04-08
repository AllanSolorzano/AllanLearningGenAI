# 04 — Retrieval Evaluation: Measuring What Gets Found

> **TL;DR:** You can't improve what you don't measure. Before tuning chunking strategies,
> embedding models, or retrieval parameters, establish a baseline metric.
> Precision@k and Recall@k are the standard measures.

---

## DevOps Analogy

Retrieval evaluation is like **SLO measurement for your search system**.

You wouldn't deploy a new service without defining what "working correctly" means. For search:
- **Precision@k** = of the k results I returned, what fraction were actually relevant? (signal-to-noise)
- **Recall@k** = of all relevant documents that exist, how many did I return in the top k? (coverage)

These are your SLIs (Service Level Indicators). Your SLO might be: "Precision@3 ≥ 0.8 and Recall@5 ≥ 0.7 on the incident query test set."

```
Precision@3 = 0.67 means:
  → For a query, I returned 3 results, 2 were relevant, 1 was noise
  → 2/3 = 67% precision

Recall@5 = 0.80 means:
  → There are 5 relevant docs for this query in the corpus
  → I retrieved 4 of them in the top 5
  → 4/5 = 80% recall
```

---

## Building a Golden Dataset

To measure retrieval, you need a **golden dataset**: a set of (query, expected_relevant_docs) pairs.

```python
GOLDEN_DATASET = [
    {
        "query": "container keeps restarting after deploy",
        "relevant_doc_ids": ["rb-001", "rb-002"],  # CrashLoopBackOff, OOMKilled
    },
    {
        "query": "cannot pull image from registry",
        "relevant_doc_ids": ["rb-006"],             # ImagePullBackOff
    },
    {
        "query": "website returning 502 errors",
        "relevant_doc_ids": ["rb-003", "rb-005"],   # Nginx 502, Node NotReady
    },
]
```

**How to build a golden dataset:**
1. Take 20–50 representative queries from your actual users (Slack, tickets, on-call logs)
2. For each query, manually identify which documents *should* be retrieved
3. Store as a JSON file, version-control it alongside your chunking and embedding code

The golden dataset is your test suite for the retrieval layer.

---

## Metrics

### Precision@k
Of the top-k retrieved documents, what fraction are in the relevant set?

```python
def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = retrieved_ids[:k]
    relevant_retrieved = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return relevant_retrieved / k
```

### Recall@k
Of all relevant documents, what fraction appear in the top-k results?

```python
def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 1.0
    top_k = set(retrieved_ids[:k])
    relevant_retrieved = len(top_k & relevant_ids)
    return relevant_retrieved / len(relevant_ids)
```

### MRR (Mean Reciprocal Rank)
Where does the first relevant result appear? Penalises systems that bury relevant docs.

```python
def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for i, doc_id in enumerate(retrieved_ids, 1):
        if doc_id in relevant_ids:
            return 1.0 / i
    return 0.0

def mrr(results: list[tuple[list[str], set[str]]]) -> float:
    return sum(reciprocal_rank(r, rel) for r, rel in results) / len(results)
```

---

## What to Optimise When Metrics Are Bad

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Low precision (noise in results) | Chunks too large, capturing unrelated content | Smaller chunks, structure-aware splitting |
| Low recall (relevant docs not found) | Query phrased differently from docs | Hybrid search (add BM25), query expansion |
| Good recall, low precision | k too large | Reduce k, add metadata filtering |
| Good metrics in test, bad in prod | Golden dataset unrepresentative | Add more diverse queries to golden set |

---

## LLM-as-Judge: Evaluating the Full Answer

Retrieval metrics measure whether you found the right documents. But even with perfect retrieval, the LLM might generate a wrong answer. **LLM-as-judge** evaluates end-to-end quality:

```python
def judge_answer(question: str, context: str, answer: str, llm) -> dict:
    prompt = f"""\
Evaluate this RAG system response.

Question: {question}
Retrieved context: {context[:1000]}
Generated answer: {answer}

Rate the answer on:
1. Faithfulness (0-3): Is the answer grounded in the context? Does it avoid hallucination?
2. Relevance (0-3): Does the answer address the question?
3. Completeness (0-3): Does the answer cover the key information in the context?

Output JSON: {{"faithfulness": 0-3, "relevance": 0-3, "completeness": 0-3, "comment": "str"}}"""

    return json.loads(llm.ask(prompt))
```

Using your LLM to evaluate your LLM output is surprisingly effective for catching hallucinations and incomplete answers, especially at scale.

---

## Key Takeaways

1. **Establish a golden dataset before tuning.** You need a baseline to know if changes help.
2. **Precision@k and Recall@k are your retrieval SLIs.** Target at least 0.7 precision@3.
3. **LLM-as-judge evaluates the full answer** — catches hallucinations that retrieval metrics miss.

---

## Hands-On

→ [Lab 04: Retrieval Evaluation](../labs/lab04_evaluation/lab.py)
