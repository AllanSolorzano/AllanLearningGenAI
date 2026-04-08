# 01 — RAG Architecture: Private Knowledge Without Fine-Tuning

> **TL;DR:** RAG (Retrieval Augmented Generation) solves the "the model doesn't know my stuff" problem.
> Retrieve relevant context from your own data → add it to the prompt → get grounded answers.
> No training, no fine-tuning, no hallucination about your private knowledge.

---

## DevOps Analogy

RAG is like **read-only database access for your LLM**.

Without RAG, the model only knows what was in its training data (the internet, public books, public code). Your runbooks, internal wikis, post-mortem database, and Terraform module docs are invisible to it.

With RAG, you give the model a read-only query interface to your knowledge base at inference time. It's not memorizing your docs — it retrieves the relevant pages and reads them in context, just like you would.

```
Without RAG:                      With RAG:
  Question → [LLM] → Answer         Question → [Search runbooks] → [LLM + results] → Answer
  (model guesses)                   (model reads actual content)
```

The database analogy extends further:

| RAG Component | Database Equivalent |
|--------------|---------------------|
| Chunking | Row normalization — splitting content into queryable units |
| Embedding | Index creation — making content searchable by meaning |
| Vector store | The index itself (like B-tree but for similarity) |
| Retrieval | SELECT WHERE similarity > threshold ORDER BY score |
| Augmented prompt | Joining retrieved rows into the query context |
| LLM generation | Application layer that interprets and presents results |

---

## Why Not Just Fine-Tune?

Fine-tuning trains new weights into the model. It's expensive, slow, and requires a lot of good labeled data. More importantly:

| Problem | Fine-tuning | RAG |
|---------|-------------|-----|
| Model doesn't know your runbooks | Expensive retraining | Add runbooks to index ✓ |
| Runbook updated | Retrain again | Re-index the changed doc ✓ |
| New service added | Retrain again | Index new docs ✓ |
| Answer needs source citation | Hard | Trivially — return the chunk ✓ |
| Cost | $10K–$100K | Fractions of a cent per query ✓ |
| Time to production | Weeks | Hours ✓ |

**Use fine-tuning when:** You need the model to internalize a new *skill* or *style* — a different reasoning pattern, consistent tone, domain-specific formatting. Not for adding facts.

**Use RAG when:** You need the model to know specific *facts* from private or frequently-updated content.

---

## The Two Phases of RAG

### Phase 1: Indexing (done once, or on document update)

```
Your documents
      ↓
[Chunker] — splits into overlapping text segments
      ↓
[Embedding model] — each chunk becomes a vector
      ↓
[Vector store] — vectors stored with metadata + original text
```

This is a batch job. Run it when:
- You first set up the system
- A document is updated
- New documents are added

### Phase 2: Querying (done per user request)

```
User question
      ↓
[Embed question] — same embedding model as Phase 1
      ↓
[Vector store search] — find top-k most similar chunks
      ↓
[Build context] — assemble chunks into the prompt (respecting context window)
      ↓
[LLM call] — generate answer grounded in retrieved context
      ↓
Answer + source references
```

---

## RAG vs Pure Retrieval vs Pure LLM

| Approach | Pros | Cons | Good for |
|----------|------|------|----------|
| Pure keyword search | Fast, no LLM cost, exact match | Misses synonyms, no synthesis | Known queries with fixed vocabulary |
| Pure LLM (no RAG) | No setup, fast | Hallucinates, no private knowledge | General questions, public knowledge |
| RAG | Private knowledge, grounded, citable | Setup required, latency for retrieval | Private docs, frequently updated content |

---

## What Can Go Wrong: The Retrieval-Generation Gap

RAG fails in two distinct ways:

**1. Retrieval failure** — the right chunk wasn't retrieved
- Cause: poor chunking, wrong embedding model, query phrased too differently from document
- Symptom: LLM says "I don't have information about that" even though the doc exists
- Fix: better chunking, query expansion, hybrid search

**2. Generation failure** — the right chunk was retrieved but the answer is wrong
- Cause: LLM ignored context, hallucinated despite context, context too noisy
- Symptom: LLM says something wrong while the correct answer is in the retrieved chunks
- Fix: stronger system prompt with "only use the provided context", reduce noise in chunks

Evaluation (Lab 04) measures both separately.

---

## Key Takeaways

1. **RAG = retrieval + in-context reading**, not memorization. The LLM reads your docs at query time.
2. **Use RAG for facts, fine-tuning for skills.** Updating knowledge = RAG. Changing behavior = fine-tuning.
3. **RAG has two failure modes** — retrieval and generation — each needs its own debugging approach.

---

## Hands-On

→ [Lab 03: Full RAG Pipeline](../labs/lab03_rag_pipeline/lab.py)  
→ [Demo: Runbook Bot](../demos/demo_runbook_bot.py)
