#!/usr/bin/env python3
"""Lab 01: Chunking Strategies — SOLUTION"""

import re
import sys

try:
    import tiktoken
    ENCODER = tiktoken.get_encoding("cl100k_base")
    def token_count(text: str) -> int:
        return len(ENCODER.encode(text))
except ImportError:
    def token_count(text: str) -> int:
        return len(text.split())


# ── Documents (same as lab.py) ─────────────────────────────────────────────────

RUNBOOK_OOMKILLED = """\
# OOMKilled — Container Out of Memory

## What Is It?
OOMKilled (exit code 137) means the Linux kernel's OOM killer terminated the container
because it exceeded its memory limit. The process was forcibly killed, not gracefully shut down.

## Symptoms
- Pod shows `OOMKilled` in `kubectl describe pod` output
- Container restarts counter incrementing
- Exit code 137 in container status
- Memory usage graphs show a spike reaching the limit before the kill

## Diagnosis

Check which container was killed and its memory limit:
```
kubectl describe pod <pod-name> -n <namespace>
```
Look for: `Last State: Terminated, Reason: OOMKilled`

Check recent memory usage:
```
kubectl top pod <pod-name> -n <namespace>
```

Check container memory limits:
```
kubectl get pod <pod-name> -o jsonpath='{.spec.containers[*].resources}'
```

## Remediation

### Short term: Increase memory limit
```yaml
resources:
  requests:
    memory: "256Mi"
  limits:
    memory: "512Mi"   # increase this value
```

Apply: `kubectl set resources deployment <name> -c=<container> --limits=memory=512Mi`

### Long term: Fix the memory leak
1. Profile with: `kubectl exec -it <pod> -- jmap -histo <pid>` (Java) or heap profiler for your language
2. Check for unclosed connections, unbounded caches, or growing in-memory state
3. Add memory metrics to dashboards: `container_memory_working_set_bytes`
4. Set up alerts at 80% of limit to get warning before OOMKill

## Prevention
- Always set both requests AND limits for production containers
- Set limit = 1.5-2× typical peak memory, not 1.0× (leaves no headroom)
- Add Prometheus alert: `container_memory_working_set_bytes / container_spec_memory_limit_bytes > 0.85`
"""

TERRAFORM_RUNBOOK = """\
# Terraform State Lock Runbook

## Overview
Terraform uses state locking to prevent concurrent modifications to infrastructure.
If a Terraform run is interrupted (network drop, kill signal, runner crash), the lock
may not be released automatically.

## Symptoms
```
Error: Error locking state: Error acquiring the state lock: ConditionalCheckFailedException
Lock Info:
  ID:        550e8400-e29b-41d4-a716-446655440000
```

## Diagnosis
Determine if the locking process is still running:
1. Check CI/CD for running pipelines with Terraform jobs
2. Check if the "Who" host is still alive and running Terraform
3. Check the lock creation time — if > 30 minutes ago, it's likely stale

## Remediation

### Safe path: Wait for the lock to clear
If another pipeline is legitimately running, wait for it to complete.
Check your CI/CD system for running Terraform jobs before proceeding.

### Force unlock (only if lock is stale)
```bash
LOCK_ID="550e8400-e29b-41d4-a716-446655440000"
terraform force-unlock $LOCK_ID
terraform plan
```

**WARNING:** Only force-unlock if you are CERTAIN no other Terraform process is running.

## Prevention
- Configure Terraform backend with DynamoDB locking (AWS) or GCS locking (GCP)
- Set pipeline timeout to automatically cancel long-running jobs
- Add lock monitoring: alert if a lock is held for > 20 minutes
"""


# ── Implementations ────────────────────────────────────────────────────────────

def fixed_size_chunk(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    words = text.split()
    step = max(1, size - overlap)
    chunks = []
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def sentence_chunk(text: str, max_tokens: int = 300) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current, count = [], [], 0
    for sentence in sentences:
        t = token_count(sentence)
        if count + t > max_tokens and current:
            chunks.append(" ".join(current))
            current, count = [], 0
        current.append(sentence)
        count += t
    if current:
        chunks.append(" ".join(current))
    return chunks


def markdown_chunk(text: str) -> list[str]:
    sections = re.split(r"\n(?=#{1,3} )", text)
    return [s.strip() for s in sections if s.strip()]


def analyse_chunks(chunks: list[str], strategy_name: str) -> None:
    if not chunks:
        print(f"  {strategy_name}: no chunks")
        return
    sizes = [token_count(c) for c in chunks]
    avg = sum(sizes) / len(sizes)
    print(f"\n  Strategy: {strategy_name}")
    print(f"  Chunks:   {len(chunks)}")
    print(f"  Tokens:   avg={avg:.0f}  min={min(sizes)}  max={max(sizes)}")
    print(f"\n  First chunk preview:")
    print(f"    '{chunks[0][:200].replace(chr(10), ' ')}...'")
    if len(chunks) > 1:
        print(f"\n  Last chunk preview:")
        print(f"    '...{chunks[-1][:200].replace(chr(10), ' ')}'")


def exercise1_compare_strategies() -> None:
    print("=" * 60)
    print("Exercise 1: Strategy Comparison on OOMKilled Runbook")
    print("=" * 60)
    doc = RUNBOOK_OOMKILLED
    total_tokens = token_count(doc)
    print(f"\nDocument: {total_tokens} tokens, {len(doc.splitlines())} lines")
    analyse_chunks(fixed_size_chunk(doc, size=150, overlap=30), "Fixed-size (150 words, 30 overlap)")
    analyse_chunks(sentence_chunk(doc, max_tokens=150), "Sentence-based (≤150 tokens)")
    analyse_chunks(markdown_chunk(doc), "Markdown-section-aware")


def exercise2_retrieval_simulation() -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: Retrieval Simulation (Keyword Proxy)")
    print("=" * 60)
    query = "container was killed because it used too much memory, how do I fix it"
    print(f"\nQuery: '{query}'")

    def keyword_score(chunk: str, q: str) -> float:
        qw = set(q.lower().split())
        cw = set(chunk.lower().split())
        return len(qw & cw) / len(qw)

    for name, chunks in [
        ("Fixed-size", fixed_size_chunk(RUNBOOK_OOMKILLED, size=150, overlap=30)),
        ("Sentence",   sentence_chunk(RUNBOOK_OOMKILLED, max_tokens=150)),
        ("Markdown",   markdown_chunk(RUNBOOK_OOMKILLED)),
    ]:
        scored = sorted([(keyword_score(c, query), c) for c in chunks], reverse=True)[:2]
        print(f"\n  {name} top-2:")
        for score, chunk in scored:
            print(f"    score={score:.2f}  '{chunk[:150].replace(chr(10), ' ')}...'")


def exercise3_overlap_matters() -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: Overlap Preserves Context")
    print("=" * 60)
    doc = TERRAFORM_RUNBOOK
    target = "terraform force-unlock"

    for label, chunks in [
        ("Without overlap", fixed_size_chunk(doc, size=200, overlap=0)),
        ("With 80-word overlap", fixed_size_chunk(doc, size=200, overlap=80)),
    ]:
        print(f"\n  {label} ({len(chunks)} chunks):")
        for i, c in enumerate(chunks):
            if target.lower() in c.lower():
                print(f"    Found in chunk {i}: '{c[:200].replace(chr(10), ' ')}...'")


def exercise4_metadata_design() -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: Chunk Metadata Design")
    print("=" * 60)

    def chunk_with_metadata(doc_text: str, doc_metadata: dict) -> list[dict]:
        raw_chunks = markdown_chunk(doc_text)
        result = []
        for i, chunk in enumerate(raw_chunks):
            # Extract the header line as section name
            first_line = chunk.splitlines()[0] if chunk.splitlines() else ""
            section = first_line.lstrip("#").strip() if first_line.startswith("#") else "body"
            result.append({
                "text": chunk,
                "metadata": {
                    **doc_metadata,
                    "chunk_index": i,
                    "chunk_tokens": token_count(chunk),
                    "section": section,
                },
            })
        return result

    doc_metadata = {
        "doc_id": "RB-002",
        "source": "runbooks/oomkilled.md",
        "team": "platform",
        "severity": "P1",
        "updated_at": "2024-09-15",
    }
    chunks = chunk_with_metadata(RUNBOOK_OOMKILLED, doc_metadata)
    for c in chunks[:3]:
        print(f"\nChunk {c['metadata']['chunk_index']}:")
        print(f"  metadata: {c['metadata']}")
        print(f"  text[:80]: {c['text'][:80].replace(chr(10), ' ')}")


def main() -> None:
    print("\nLab 01: Chunking Strategies (Solution)\n")
    exercise1_compare_strategies()
    exercise2_retrieval_simulation()
    exercise3_overlap_matters()
    exercise4_metadata_design()
    print("\n" + "=" * 60)
    print("Key takeaways:")
    print("  1. Markdown-section chunking preserves semantic units for runbooks.")
    print("  2. Fixed-size is simple but cuts mid-thought — use with overlap.")
    print("  3. Always attach metadata for filtering and source attribution.")
    print("=" * 60)


if __name__ == "__main__":
    main()
