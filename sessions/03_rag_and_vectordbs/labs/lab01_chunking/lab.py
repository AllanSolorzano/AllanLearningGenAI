#!/usr/bin/env python3
"""
Lab 01: Chunking Strategies
=============================
How you split documents is the biggest lever on RAG quality.
In this lab you'll implement three chunking strategies and compare
which produces the best chunks for retrieval.

No API key required. No Ollama required. Pure offline Python.

Run:
    python lab.py

When stuck: check solution.py
"""

import re
import sys

# We'll use tiktoken to count tokens in chunks
try:
    import tiktoken
    ENCODER = tiktoken.get_encoding("cl100k_base")
    def token_count(text: str) -> int:
        return len(ENCODER.encode(text))
except ImportError:
    print("WARNING: tiktoken not installed — using word count as proxy")
    def token_count(text: str) -> int:
        return len(text.split())


# ── Sample documents ───────────────────────────────────────────────────────────
# Realistic runbook and post-mortem documents of different lengths and structures.

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

POSTMORTEM_PAYMENT = """\
# Post-Mortem: Payment Service Outage — 2024-10-15

## Incident Summary
Duration: 47 minutes (14:23 UTC to 15:10 UTC)
Severity: P1
Impact: 100% of checkout transactions failed. Estimated revenue impact: $127,000.
On-call: @alice (primary), @bob (escalation)

## Timeline

14:21  Marketing team launched FLASH50 campaign (50% off all items). No engineering review.
14:22  Order rate: 450/min → 2,800/min (+522% in 60 seconds)
14:23  checkout-service CPU 23% → 87%. Connection pool errors begin.
14:24  payment-service: auth unavailable, 100% checkout failures begin.
14:25  Alertmanager fires: PaymentServiceDown (P1 declared)
14:28  On-call acknowledges. Begins investigation.
14:35  Root cause identified: auth-service connection pool exhausted (size 20, 2800 req/min)
14:40  Decision: emergency scale auth-service to 20 replicas
14:45  auth-service replicas: 4 → 20 (scaling complete)
14:52  Error rate drops from 100% to 12%. Still elevated.
14:58  CPU stabilises. Connection pool errors stop.
15:10  Error rate returns to baseline (<0.1%). Incident resolved.

## Root Cause
Traffic spike from marketing campaign caused auth-service connection pool exhaustion.
Auth-service had no HPA configured and a connection pool size of 20 that predated
the current traffic levels. 2,800 requests/min with 4 pods and 20 connections/pod
= insufficient capacity for 6.25× traffic increase.

## Contributing Factors
1. No HPA on auth-service — manual scaling only
2. Marketing campaign launched without capacity review or engineering notification
3. Connection pool size (20) not reviewed since service launched in 2022
4. No runbook for "traffic spike + auth degraded" scenario

## Action Items
| Action | Owner | Due | Status |
|--------|-------|-----|--------|
| Add HPA to auth-service (target CPU 60%) | @alice | 2024-10-18 | DONE |
| Require engineering review for campaigns >20% traffic increase | @carol (EM) | 2024-10-22 | IN PROGRESS |
| Review connection pool sizes for all services | @bob | 2024-10-25 | TODO |
| Add runbook: traffic spike response | @alice | 2024-10-20 | DONE |
| Add alert: connection pool utilisation >70% | @alice | 2024-10-18 | DONE |

## What Went Well
- P1 was declared quickly (3 minutes after symptoms started)
- Root cause identified in 10 minutes
- Clear communication in incident channel throughout

## Lessons Learned
- Marketing and engineering need a shared runbook for campaign launches
- HPA should be standard for all stateless services; exceptions require explicit justification
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
  Path:      s3://my-terraform-state/prod/terraform.tfstate
  Operation: OperationTypePlan
  Who:       ci-runner@gitlab-runner-7d9f2
  Version:   1.6.0
  Created:   2024-10-15 14:23:01.123 UTC
  Info:
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
# Get the lock ID from the error message
LOCK_ID="550e8400-e29b-41d4-a716-446655440000"

# Force unlock — THIS IS IRREVERSIBLE
terraform force-unlock $LOCK_ID

# Verify the lock is cleared
terraform plan
```

**WARNING:** Only force-unlock if you are CERTAIN no other Terraform process is running.
Force-unlocking while another process is writing state can corrupt the state file.

## Prevention
- Configure Terraform backend with DynamoDB locking (AWS) or GCS locking (GCP)
- Set pipeline timeout to automatically cancel long-running jobs
- Add lock monitoring: alert if a lock is held for > 20 minutes
- Use Atlantis or Terraform Cloud for managed state locking

## State File Corruption Recovery
If state corruption occurs after a force-unlock:
1. Check S3 versioning for the previous state: `aws s3api list-object-versions --bucket my-terraform-state`
2. Restore previous version: `aws s3api copy-object --copy-source my-bucket/path?versionId=<id>`
3. Validate: `terraform plan` — review carefully before applying
"""


# ── Chunking implementations ───────────────────────────────────────────────────

def fixed_size_chunk(text: str, size: int = 400, overlap: int = 50) -> list[str]:
    """Split text into fixed-size chunks (in words) with overlap.

    This is the simplest approach. It ignores sentence and paragraph boundaries.
    """
    # TODO 1: Implement fixed-size chunking.
    # Split the text into words, then create windows of `size` words,
    # advancing by (size - overlap) words each step.
    #
    # Steps:
    #   words = text.split()
    #   step = size - overlap
    #   for start in range(0, len(words), step):
    #       chunk = ' '.join(words[start:start + size])
    #       if chunk: chunks.append(chunk)
    pass


def sentence_chunk(text: str, max_tokens: int = 300) -> list[str]:
    """Split text at sentence boundaries, grouping sentences up to max_tokens.

    Preserves sentence integrity — no mid-sentence cuts.
    """
    # TODO 2: Implement sentence-based chunking.
    # Steps:
    #   1. Split text into sentences using: re.split(r'(?<=[.!?])\s+', text)
    #   2. Group consecutive sentences until the group exceeds max_tokens
    #   3. When a group exceeds max_tokens, save it and start a new group
    #   4. Return list of sentence-group strings
    pass


def markdown_chunk(text: str) -> list[str]:
    """Split a Markdown document at header boundaries (##, ###).

    Each section (from one header to the next) becomes a chunk.
    This preserves the semantic structure of the document.
    """
    # TODO 3: Implement markdown-aware chunking.
    # Steps:
    #   1. Split on lines that start with '#' using re.split(r'\n(?=#{1,3} )', text)
    #   2. Strip each section
    #   3. Filter out empty sections
    #   4. Return the list of sections
    pass


# ── Analysis helpers ──────────────────────────────────────────────────────────

def analyse_chunks(chunks: list[str], strategy_name: str) -> None:
    """Print statistics about a set of chunks."""
    if not chunks:
        print(f"  {strategy_name}: no chunks produced (TODO not complete)")
        return

    sizes = [token_count(c) for c in chunks]
    avg = sum(sizes) / len(sizes)
    min_s, max_s = min(sizes), max(sizes)

    print(f"\n  Strategy: {strategy_name}")
    print(f"  Chunks:   {len(chunks)}")
    print(f"  Tokens:   avg={avg:.0f}  min={min_s}  max={max_s}")
    print(f"\n  First chunk preview:")
    preview = chunks[0][:200].replace('\n', ' ')
    print(f"    '{preview}...'")
    if len(chunks) > 1:
        print(f"\n  Last chunk preview:")
        preview = chunks[-1][:200].replace('\n', ' ')
        print(f"    '...{preview}'")


# ── Exercises ─────────────────────────────────────────────────────────────────

def exercise1_compare_strategies() -> None:
    """Exercise 1: Compare all 3 chunking strategies on the same document."""
    print("=" * 60)
    print("Exercise 1: Strategy Comparison on OOMKilled Runbook")
    print("=" * 60)

    doc = RUNBOOK_OOMKILLED
    total_tokens = token_count(doc)
    print(f"\nDocument: {total_tokens} tokens, {len(doc.split(chr(10)))} lines")

    # TODO 4: Call each chunking function and pass results to analyse_chunks
    chunks_fixed = fixed_size_chunk(doc, size=150, overlap=30)
    chunks_sentence = sentence_chunk(doc, max_tokens=150)
    chunks_markdown = markdown_chunk(doc)

    analyse_chunks(chunks_fixed, "Fixed-size (150 words, 30 overlap)")
    analyse_chunks(chunks_sentence, "Sentence-based (≤150 tokens)")
    analyse_chunks(chunks_markdown, "Markdown-section-aware")


def exercise2_retrieval_simulation() -> None:
    """Exercise 2: Simulate which chunks would be retrieved for a query.

    We don't have an actual vector store here — we use simple keyword overlap
    as a stand-in to illustrate how chunk quality affects retrieval.
    """
    print("\n" + "=" * 60)
    print("Exercise 2: Retrieval Simulation (Keyword Proxy)")
    print("=" * 60)

    query = "container was killed because it used too much memory, how do I fix it"
    print(f"\nQuery: '{query}'")

    def keyword_score(chunk: str, query: str) -> float:
        q_words = set(query.lower().split())
        c_words = set(chunk.lower().split())
        return len(q_words & c_words) / len(q_words)

    # TODO 5: For each chunking strategy, get the top-2 chunks by keyword score.
    # Print the strategy name, score, and first 150 chars of each top chunk.
    # This shows how different strategies affect which content gets retrieved.

    for strategy_name, chunks in [
        ("Fixed-size", fixed_size_chunk(RUNBOOK_OOMKILLED, size=150, overlap=30) or []),
        ("Sentence",   sentence_chunk(RUNBOOK_OOMKILLED, max_tokens=150) or []),
        ("Markdown",   markdown_chunk(RUNBOOK_OOMKILLED) or []),
    ]:
        if not chunks:
            print(f"\n  {strategy_name}: (TODO not complete)")
            continue

        scored = [(keyword_score(c, query), c) for c in chunks]
        scored.sort(reverse=True)
        top = scored[:2]

        print(f"\n  {strategy_name} top-2 chunks:")
        for score, chunk in top:
            preview = chunk[:150].replace('\n', ' ')
            print(f"    score={score:.2f}  '{preview}...'")


def exercise3_overlap_matters() -> None:
    """Exercise 3: Show that overlap preserves context across chunk boundaries.

    Find a sentence that would be split differently with 0 vs 20% overlap.
    """
    print("\n" + "=" * 60)
    print("Exercise 3: Overlap Preserves Context")
    print("=" * 60)

    doc = TERRAFORM_RUNBOOK

    # TODO 6: Compare fixed_size_chunk with overlap=0 vs overlap=80
    # For each, find and print the chunk boundary where the most
    # important content (the force-unlock command) falls.
    no_overlap = fixed_size_chunk(doc, size=200, overlap=0) or []
    with_overlap = fixed_size_chunk(doc, size=200, overlap=80) or []

    target = "terraform force-unlock"

    print(f"\nSearching for '{target}' in chunks...")
    print(f"\n  Without overlap ({len(no_overlap)} chunks):")
    for i, chunk in enumerate(no_overlap):
        if target.lower() in chunk.lower():
            print(f"    Found in chunk {i}: '{chunk[:200].replace(chr(10), ' ')}...'")

    print(f"\n  With 80-word overlap ({len(with_overlap)} chunks):")
    for i, chunk in enumerate(with_overlap):
        if target.lower() in chunk.lower():
            print(f"    Found in chunk {i}: '{chunk[:200].replace(chr(10), ' ')}...'")


def exercise4_metadata_design() -> None:
    """Exercise 4: Design the metadata schema for your chunks.

    Metadata allows filtering in the vector store — only search runbooks for team X,
    or only search docs updated in the last 90 days.
    """
    print("\n" + "=" * 60)
    print("Exercise 4: Chunk Metadata Design")
    print("=" * 60)

    # TODO 7: Write a function chunk_with_metadata(doc_text, doc_metadata)
    # that returns a list of dicts: {"text": str, "metadata": dict}
    # where metadata includes the doc-level metadata PLUS chunk-level info:
    #   - chunk_index: int (position of this chunk in the document)
    #   - chunk_tokens: int (token count of this chunk)
    #   - section: str (the markdown header, if applicable)
    #
    # Then print the metadata for the first 3 chunks of RUNBOOK_OOMKILLED.

    doc_metadata = {
        "doc_id": "RB-002",
        "source": "runbooks/oomkilled.md",
        "team": "platform",
        "severity": "P1",
        "updated_at": "2024-09-15",
    }

    # Your implementation here
    # chunks_with_meta = chunk_with_metadata(RUNBOOK_OOMKILLED, doc_metadata)
    # for i, c in enumerate(chunks_with_meta[:3]):
    #     print(f"\nChunk {i}:")
    #     print(f"  metadata: {c['metadata']}")
    #     print(f"  text[:80]: {c['text'][:80].replace(chr(10), ' ')}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 01: Chunking Strategies\n")
    exercise1_compare_strategies()
    exercise2_retrieval_simulation()
    exercise3_overlap_matters()
    exercise4_metadata_design()

    print("\n" + "=" * 60)
    print("Key takeaways:")
    print("  1. Markdown-section chunking preserves semantic units for runbooks.")
    print("  2. Fixed-size is simple but cuts mid-thought — use with overlap.")
    print("  3. Chunk size vs quality: too large = noise, too small = no context.")
    print("  4. Always attach metadata — you'll need it for filtering and citations.")
    print("=" * 60)


if __name__ == "__main__":
    main()
