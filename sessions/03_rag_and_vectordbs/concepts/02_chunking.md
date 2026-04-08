# 02 — Chunking: Splitting Documents for Retrieval

> **TL;DR:** How you split documents is the single biggest lever on RAG quality.
> Too large = irrelevant content dilutes good content. Too small = loses context.
> The right chunk contains exactly one retrievable idea.

---

## DevOps Analogy

Chunking is like **log rotation and retention policy**.

You don't keep one infinite log file — you split logs into manageable units. But you also don't split every single line into its own file. The chunk size depends on what you query against it.

```
Too large (one file for all logs):
  grep "OOM" /var/log/all-application-logs-ever.log
  → Returns 40,000 lines — drowning in noise

Too small (one file per log line):
  → 10 million files, no context between related events

Right size (one file per hour, with overlap):
  → The OOM event is found with its surrounding context intact
```

For RAG documents:
- **Too large**: "Our entire Kubernetes runbook (50 pages)" as one chunk. The relevant 3 sentences about OOMKilled are lost in 40,000 tokens of noise.
- **Too small**: Every sentence as a separate chunk. Retrieves "Increase the memory limit" with no context about when or why.
- **Right size**: One section per failure mode, ~300-500 tokens, with a bit of surrounding context.

---

## Chunking Strategies

### Strategy 1: Fixed-Size (Simplest)

Split at every N characters or tokens, with overlap:

```python
def fixed_size_chunks(text: str, size: int = 512, overlap: int = 64) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap  # overlap preserves context across boundaries
    return chunks
```

**Pros:** Simple, predictable, easy to implement  
**Cons:** Cuts mid-sentence, mid-paragraph — breaks semantic units  
**Use when:** Quick prototype, or when document structure is unknown

### Strategy 2: Sentence-Based

Split at sentence boundaries:

```python
import re

def sentence_chunks(text: str, max_tokens: int = 300) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current, count = [], [], 0
    for sentence in sentences:
        tokens = len(sentence.split())  # approximate
        if count + tokens > max_tokens and current:
            chunks.append(' '.join(current))
            current, count = [], 0
        current.append(sentence)
        count += tokens
    if current:
        chunks.append(' '.join(current))
    return chunks
```

**Pros:** Preserves sentence integrity, readable chunks  
**Cons:** Sentences don't always align with topical boundaries  
**Use when:** Prose documents, wiki articles, post-mortems

### Strategy 3: Markdown/Structure-Aware (Best for runbooks)

Split on document structure — headers, sections, bullet lists:

```python
def markdown_chunks(text: str) -> list[str]:
    # Split at H2 and H3 headers — each section becomes a chunk
    sections = re.split(r'\n#{1,3} ', text)
    return [s.strip() for s in sections if s.strip()]
```

**Pros:** Each chunk = one topic, preserves the natural document structure  
**Cons:** Requires structured input (Markdown, RST, HTML)  
**Use when:** Runbooks, API docs, wikis — anything with headers

### Strategy 4: Recursive / Hierarchical

Modern approach: try to split at paragraph boundaries first, then sentences, then words:

```
Split order:
  1. Try "\n\n" (paragraph) — ideal, preserves full thought
  2. Try "\n" (newline) — good for bullet lists
  3. Try ". " (sentence) — fallback
  4. Try " " (word) — last resort
```

This is what LangChain's `RecursiveCharacterTextSplitter` implements. It produces the most semantically coherent chunks.

---

## The Overlap Problem

Without overlap, context that straddles a chunk boundary is lost:

```
Chunk A ends with: "...increase the CPU limit to at least"
Chunk B starts with: "500m for the payment service containers."
```

Neither chunk is queryable on its own. With 20% overlap:
```
Chunk A: "...increase the CPU limit to at least 500m for"
Chunk B: "CPU limit to at least 500m for the payment service containers."
```

Both chunks now contain the complete idea. Standard overlap: 10–20% of chunk size.

---

## Chunk Metadata: The Often-Forgotten Part

Every chunk should carry metadata that helps with:
- Source attribution ("this answer came from runbook RB-042")
- Filtering ("only search production runbooks, not staging")
- Re-ranking ("prefer more recently updated docs")

```python
chunk = {
    "text": "OOMKilled: Increase the memory limit...",
    "metadata": {
        "source": "runbook/oomkilled.md",
        "section": "Remediation",
        "doc_id": "RB-002",
        "updated_at": "2024-09-15",
        "tags": ["kubernetes", "memory", "production"],
    }
}
```

ChromaDB stores this metadata alongside the vector and lets you filter on it at query time.

---

## Chunk Size Reference

| Content Type | Recommended Size | Why |
|-------------|-----------------|-----|
| Runbooks (structured) | 200–400 tokens | One remediation step per chunk |
| Incident post-mortems | 300–600 tokens | One timeline section per chunk |
| API documentation | 150–300 tokens | One endpoint or method per chunk |
| Code (functions) | Whole function | Don't split within a function |
| Terraform modules | Whole resource block | Context spans the full resource |
| Log analysis | 1–3 log events | Too small = no context; too big = noise |

---

## Key Takeaways

1. **Chunking strategy = the biggest RAG quality lever.** Test it. Measure retrieval quality before optimising anything else.
2. **Use structure-aware chunking for structured docs.** Markdown headers → one chunk per section.
3. **Always add metadata.** Source attribution, timestamps, tags — you'll need them for filtering and citations.

---

## Hands-On

→ [Lab 01: Chunking Strategies](../labs/lab01_chunking/lab.py)
