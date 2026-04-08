# 02 — Embeddings: Meaning as Math

> **TL;DR:** Embeddings turn text into vectors of numbers. Similar meanings produce similar vectors.
> This lets you do math on *meaning* — enabling semantic search, clustering, and anomaly detection.

---

## DevOps Analogy

Think of **Kubernetes labels and selectors**.

When you label a pod `app=nginx, tier=frontend, env=production`, you're assigning it a position in a multi-dimensional "meaning space." Pods with similar labels are conceptually close to each other. `kubectl get pods -l app=nginx,env=production` finds pods by their *semantic position*, not by string-matching their name.

Embeddings do the same thing for text meaning — but instead of 3-4 label dimensions, they use 384–4096 dimensions. The model has learned that pods, containers, and Kubernetes are semantically "nearby," while gradient descent and backpropagation are in a different neighborhood.

A simpler analogy: **GPS coordinates**. A lat/long pair encodes a physical location in 2D space. An embedding encodes semantic meaning in N-dimensional space. "pod crashlooping" and "container restarting" will have GPS coordinates close together. "pod crashlooping" and "S3 bucket policy" will be far apart.

---

## What Is an Embedding?

An embedding is a fixed-size array of floating-point numbers that represents a piece of text:

```python
"pod crashlooping in production"
→ [0.23, -0.45, 0.12, 0.88, -0.03, ..., 0.67]  # 384 numbers
```

The numbers themselves are not interpretable individually — no single dimension means "is this about Kubernetes?" The *pattern* of all 384 (or 768, or 1536) numbers together encodes the semantic content.

Two embeddings are compared using **cosine similarity**: how closely do these two vectors point in the same direction?

```
cosine_similarity("pod OOMKilled", "container killed for exceeding memory limit") = 0.94
cosine_similarity("pod OOMKilled", "S3 bucket access denied")                     = 0.08
```

Cosine similarity ranges from -1 (opposite meanings) to 1 (identical meaning). In practice, values above 0.7 indicate strong semantic similarity.

---

## How Embeddings Are Created

1. **Tokenize** the input text (see Concept 01)
2. Each token ID is looked up in an **embedding table** (a learned matrix mapping token ID → dense vector)
3. These token embeddings pass through the transformer layers
4. The **final layer's output** (often the `[CLS]` token or the mean of all tokens) becomes the sentence embedding

For a dedicated embedding model like `all-MiniLM-L6-v2` (used in Lab 02), the model is specifically trained to produce sentence-level embeddings where semantic similarity maps to vector similarity.

---

## Why This Matters for DevOps Engineers

### Semantic log search
Instead of `grep "connection refused"`, you can search by *meaning*:

```
Query: "database connection failed"

Keyword search finds:  Lines containing "database" AND "connection" AND "failed"
Semantic search finds: "psycopg2.OperationalError: could not connect to server"
                       "upstream host is unreachable"
                       "dial tcp: connection refused"
```

All of those are semantically the same problem, even though they share few words.

### Runbook retrieval
Embed all your runbooks once, store the vectors. When an alert fires, embed the alert description and find the most similar runbook — automatically, without keyword templates.

### Incident correlation
Embed historical incident descriptions. When a new incident comes in, find the 3 most similar past incidents. Surface their root causes and resolutions automatically.

### Anomaly detection in logs
Embed "normal" log patterns. New log entries that have embeddings far from the normal cluster are potential anomalies. This is a geometric way to detect unusual behavior.

---

## Semantic vs Keyword Search: A Concrete Comparison

**Corpus:** 5 runbook titles  
**Query:** "my service keeps restarting"

| Rank | Keyword Search | Semantic Search |
|------|----------------|-----------------|
| 1 | (no matches — none contain "keeps restarting") | "Pod CrashLoopBackOff Runbook" (0.89) |
| 2 | — | "Container OOMKilled Runbook" (0.71) |
| 3 | — | "Service Unavailable Runbook" (0.54) |

Keyword search fails completely. Semantic search surfaces the right answer even with different vocabulary.

---

## Embedding Models

| Model | Dimensions | Size | Speed | Use Case |
|-------|-----------|------|-------|----------|
| `all-MiniLM-L6-v2` | 384 | 80MB | Fast (CPU) | Learning, prototyping |
| `all-mpnet-base-v2` | 768 | 420MB | Medium | Better quality, still local |
| OpenAI `text-embedding-3-small` | 1536 | API | API call | Production, no GPU needed |
| Anthropic Voyage | 1024 | API | API call | Production, Claude ecosystem |

For Lab 02, we use `all-MiniLM-L6-v2` — it runs entirely on CPU, downloads once (~80MB), and is fast enough to embed hundreds of sentences in seconds.

---

## Key Takeaways

1. **Embeddings encode meaning as coordinates in high-dimensional space.** Similar meanings → nearby coordinates.
2. **Cosine similarity measures semantic relatedness** — use it, not Euclidean distance, for text.
3. **Semantic search is fundamentally different from keyword search** — it understands meaning, not just character patterns.

---

## Hands-On

→ [Lab 02: Embeddings](../labs/lab02_embeddings/lab.py)  
→ [Demo: Semantic Search](../demos/demo_semantic_search.py)
