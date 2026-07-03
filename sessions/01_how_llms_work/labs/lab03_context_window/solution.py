#!/usr/bin/env python3
"""
Lab 03: Context Window Management — SOLUTION
==============================================
Reference implementation. Try to complete lab.py yourself before reading this.
"""

import tiktoken

ENCODER = tiktoken.get_encoding("cl100k_base")

MODEL_LIMITS = {
    "gpt-3.5-turbo":      16_384,
    "gpt-4o":            128_000,
    "claude-haiku":      200_000,
    "claude-sonnet":     200_000,
    "llama-3-8b-local":    8_192,
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def count_tokens(text: str) -> int:
    return len(ENCODER.encode(text))


def count_message_tokens(message: dict) -> int:
    return count_tokens(message["content"]) + 4


def count_conversation_tokens(messages: list[dict], system_prompt: str = "") -> int:
    total = count_tokens(system_prompt) if system_prompt else 0
    total += sum(count_message_tokens(m) for m in messages)
    return total


def remaining_budget(
    messages: list[dict],
    system_prompt: str,
    model: str,
    reserve_for_response: int = 1024,
) -> int:
    used = count_conversation_tokens(messages, system_prompt)
    return MODEL_LIMITS[model] - used - reserve_for_response


def trim_to_fit(
    messages: list[dict],
    system_prompt: str,
    model: str,
    reserve_for_response: int = 1024,
) -> list[dict]:
    trimmed = list(messages)  # work on a copy
    while len(trimmed) > 1 and remaining_budget(trimmed, system_prompt, model, reserve_for_response) < 0:
        trimmed.pop(0)  # drop oldest message
    return trimmed


# ── Exercises ─────────────────────────────────────────────────────────────────

def exercise1_count_and_budget(system_prompt: str) -> None:
    print("=" * 60)
    print("Exercise 1: Token Counting and Budget Analysis")
    print("=" * 60)

    system_prompts = {
        "Minimal":   "You are a helpful assistant.",
        "Basic SRE": system_prompt,
        "Detailed": """\
You are a senior Site Reliability Engineer with 10 years of experience.
You specialize in Kubernetes, AWS infrastructure, and observability.
You analyze incidents, suggest root causes, and recommend remediation steps.
Always reference specific Kubernetes commands or AWS CLI commands.
Structure your responses with: Summary, Root Cause Analysis, Immediate Actions, Long-term Fix.
Keep responses concise — under 500 words unless deep analysis is explicitly requested.
When you don't know something, say so rather than guessing.
Prioritize safety: never recommend actions that could cause data loss without explicit warnings.""",
    }

    retrieved_runbook = """\
Runbook: Database Connection Pool Exhausted
Severity: P1
Last updated: 2024-09-12
Steps:
1. Check pg_stat_activity: SELECT count(*), state FROM pg_stat_activity GROUP BY state;
2. Identify long-running queries: SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state = 'active' ORDER BY duration DESC LIMIT 10;
3. Kill blocking queries if necessary: SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE duration > interval '5 minutes';
4. Check application connection pool settings in config/database.yml
5. If pool exhaustion persists, scale horizontally or add PgBouncer"""

    print(f"\n{'System Prompt':<15} {'Tokens':>8}")
    print("─" * 28)
    for name, prompt in system_prompts.items():
        tokens = count_tokens(prompt)
        print(f"{name:<15} {tokens:>8}")

    print(f"\nRetrieved runbook: {count_tokens(retrieved_runbook)} tokens")
    print(f"\nContext budget remaining (per model, with 'Basic SRE' prompt + runbook):")

    base_messages = [
        {"role": "user", "content": "We're seeing high error rates on the payment service. Here's what I found:\n" + retrieved_runbook},
    ]

    for model_name, limit in MODEL_LIMITS.items():
        budget = remaining_budget(base_messages, system_prompt, model_name)
        status = "OK" if budget > 0 else "OVER LIMIT"
        print(f"  {model_name:<25} {limit:>8} limit   {budget:>8} remaining   {status}")


def exercise2_conversation_growth(system_prompt: str) -> None:
    print("\n" + "=" * 60)
    print("Exercise 2: Conversation Growth Over Time")
    print("=" * 60)

    conversation_turns = [
        ("user",      "We have a P1 incident — the payment service is returning 503s. Started about 15 minutes ago."),
        ("assistant", "Understood, P1 in progress. First: what's the current error rate? Check your APM or run: kubectl top pods -n payments | sort -k3 -rn"),
        ("user",      "Error rate is at 87%. kubectl shows payment-api pods are all in Running state but CPU is at 340% of requests (limit is 500m). Memory looks normal at 180Mi/512Mi limit."),
        ("assistant", "CPU throttling is the likely culprit. At 340% of requests with a 500m limit, pods are being heavily throttled. Quick check: kubectl exec -it <payment-pod> -- cat /sys/fs/cgroup/cpu/cpu.stat | grep throttled — if throttled_time is growing rapidly, confirmed. Immediate action: kubectl patch deployment payment-api -p '{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"payment-api\",\"resources\":{\"limits\":{\"cpu\":\"1000m\"}}}]}}}}'"),
        ("user",      "throttled_time is growing fast. Applied the patch. Pods are restarting. New pods coming up but still showing high CPU. Error rate at 72% — improving but slowly."),
        ("assistant", "Good progress. While pods recover: check if there's a traffic spike causing this. Run: kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/payments/pods | jq '.items[] | {name: .metadata.name, cpu: .containers[0].usage.cpu}'. Also check if a recent deployment correlates: kubectl rollout history deployment/payment-api"),
        ("user",      "No deployment in last 6 hours. But I see in the metrics that request rate doubled starting 15 minutes ago — same time as the incident. Looks like a traffic spike from a marketing campaign that went live."),
        ("assistant", "Traffic spike confirms the cause. Immediate mitigations: (1) HPA check: kubectl get hpa -n payments — if min replicas is too low, patch it: kubectl patch hpa payment-api -p '{\"spec\":{\"minReplicas\":6}}'. (2) Scale manually now: kubectl scale deployment payment-api --replicas=8. (3) If you have cluster autoscaler: check node count: kubectl get nodes. Traffic doubles = roughly double the replicas as a starting point."),
        ("user",      "Scaled to 8 replicas. Error rate dropping — now at 23%. Nodes are auto-scaling, 2 new nodes coming up. I think we're stabilizing. How do I prevent this next time?"),
        ("assistant", "Great recovery! For prevention: (1) HPA with CPU target: configure target CPU at 60-70% not 80%+ to give headroom. (2) Load test before campaigns: coordinate with marketing for traffic forecasts. (3) Add KEDA for event-driven scaling if you have queue-based workloads. (4) Set up alerts at 60% CPU throttle (not 100%). (5) Document this incident and add campaign traffic to your capacity planning process. Write a blameless post-mortem — this was a coordination gap, not a technical failure."),
        ("user",      "Error rate is now 2% and falling. Incident resolved. Thanks. Can you help me draft the post-mortem summary?"),
    ]

    messages: list[dict] = []
    model = "llama-3-8b-local"

    print(f"\nModel: {model} (context limit: {MODEL_LIMITS[model]:,} tokens)")
    print(f"System prompt: {count_tokens(system_prompt)} tokens")
    print()
    print(f"{'Turn':<6} {'Role':<12} {'Msg Tokens':>11} {'Total Tokens':>13} {'Remaining':>10} {'Status'}")
    print("─" * 70)

    for i, (role, content) in enumerate(conversation_turns):
        messages.append({"role": role, "content": content})
        msg_tokens = count_message_tokens({"role": role, "content": content})
        total_tokens = count_conversation_tokens(messages, system_prompt)
        budget_remaining = remaining_budget(messages, system_prompt, model)
        status = "OK" if budget_remaining >= 0 else "OVER LIMIT — trim needed"
        print(f"{i+1:<6} {role:<12} {msg_tokens:>11} {total_tokens:>13} {budget_remaining:>10}  {status}")


def exercise3_sliding_window(system_prompt: str) -> None:
    print("\n" + "=" * 60)
    print("Exercise 3: Sliding Window Trimming")
    print("=" * 60)

    long_conversation: list[dict] = []
    for i in range(20):
        long_conversation.append({
            "role": "user",
            "content": f"Message {i+1}: Can you check the status of deployment-{i+1:03d} in the staging namespace and tell me if all pods are healthy? Also check the last 50 log lines for any errors.",
        })
        long_conversation.append({
            "role": "assistant",
            "content": f"Checked deployment-{i+1:03d} in staging. All 3/3 pods are Running and Ready. No errors in the last 50 log lines. CPU at ~45% of request, memory at ~62% of limit. Last deploy was 2 hours ago by CI pipeline. Status: HEALTHY.",
        })

    model = "llama-3-8b-local"
    total_before = count_conversation_tokens(long_conversation, system_prompt)

    print(f"\nFull conversation: {len(long_conversation)} messages, {total_before:,} tokens")
    print(f"Model limit:       {MODEL_LIMITS[model]:,} tokens")
    print(f"System prompt:     {count_tokens(system_prompt):,} tokens")
    print(f"Over limit by:     {total_before - MODEL_LIMITS[model] + 1024:,} tokens")

    trimmed = trim_to_fit(long_conversation, system_prompt, model)
    total_after = count_conversation_tokens(trimmed, system_prompt)
    dropped = len(long_conversation) - len(trimmed)

    print(f"\nAfter trimming:")
    print(f"  Messages: {len(long_conversation)} → {len(trimmed)} (dropped {dropped})")
    print(f"  Tokens:   {total_before:,} → {total_after:,}")
    print(f"  Remaining budget: {remaining_budget(trimmed, system_prompt, model):,} tokens")

    print(f"\nFirst message kept: \"{trimmed[0]['content'][:80]}...\"")
    print(f"Last message kept:  \"{trimmed[-1]['content'][:80]}...\"")
    print("\nNote: The most recent messages are preserved; oldest are dropped.")


def exercise4_budget_aware_rag(system_prompt: str) -> None:
    print("\n" + "=" * 60)
    print("Exercise 4: Budget-Aware Document Inclusion (RAG Pattern)")
    print("=" * 60)

    retrieved_docs = [
        {"id": "RB-001", "relevance": 0.94, "content": "CrashLoopBackOff Runbook: A pod in CrashLoopBackOff is repeatedly starting and crashing. Check logs with kubectl logs <pod> --previous. Common causes: application crash, missing ConfigMap or Secret, or OOMKilled. Fix the application error or increase memory limits."},
        {"id": "RB-009", "relevance": 0.87, "content": "Database Connection Pool Exhausted: The application cannot acquire a database connection. Check pg_stat_activity for active connections. Short term: increase max_connections or pool size. Long term: add a connection pooler like PgBouncer."},
        {"id": "RB-003", "relevance": 0.72, "content": "Nginx 502 Bad Gateway: 502 Bad Gateway means nginx cannot reach the upstream service. Verify backend pods are running and passing health checks. Check nginx error logs and upstream service logs for connection errors."},
        {"id": "KB-014", "relevance": 0.65, "content": "Kubernetes Pod Lifecycle Guide: Pods go through phases: Pending, Running, Succeeded, Failed, Unknown. ContainerStatuses shows individual container states. Use kubectl describe pod for detailed events. Events section shows scheduling decisions, image pull attempts, and container start failures."},
        {"id": "KB-022", "relevance": 0.58, "content": "Database Performance Tuning: For PostgreSQL, key metrics are: cache hit ratio (should be >99%), index scan ratio, lock wait time, and connection count. Enable pg_stat_statements for query-level metrics. Use EXPLAIN ANALYZE for slow query investigation."},
        {"id": "KB-031", "relevance": 0.45, "content": "Kubernetes Resource Management: Requests are what a container is guaranteed. Limits are the maximum allowed. CPU throttling happens when a container hits its CPU limit. OOMKill happens when it hits its memory limit. Always set both requests and limits for production workloads."},
        {"id": "KB-047", "relevance": 0.38, "content": "Incident Management Process: P1 incidents require a declared incident commander. Page the on-call team. Open a Slack incident channel. Run a 30-minute status cadence. Document timeline in the incident doc. Conduct blameless post-mortem within 5 business days."},
    ]

    current_messages = [
        {"role": "user", "content": "Our payment service is crashing repeatedly. The pods keep restarting and I see database connection errors in the logs."},
    ]

    model = "gpt-3.5-turbo"
    user_query_tokens = count_message_tokens(current_messages[0])
    reserve = 1024
    base_tokens = count_tokens(system_prompt) + user_query_tokens + reserve

    print(f"\nModel: {model} (limit: {MODEL_LIMITS[model]:,} tokens)")
    print(f"Base tokens (system + query + response reserve): {base_tokens:,}")
    print(f"Budget for documents: {MODEL_LIMITS[model] - base_tokens:,} tokens")
    print()

    included_docs = []
    tokens_used = 0

    for doc in retrieved_docs:
        doc_tokens = count_tokens(doc["content"])
        if base_tokens + tokens_used + doc_tokens <= MODEL_LIMITS[model]:
            included_docs.append(doc)
            tokens_used += doc_tokens

    print(f"{'ID':<10} {'Relevance':>10} {'Tokens':>8} {'Included':>10}")
    print("─" * 44)
    for doc in retrieved_docs:
        included = doc in included_docs
        doc_tokens = count_tokens(doc["content"])
        marker = "YES" if included else "no (budget)"
        print(f"{doc['id']:<10} {doc['relevance']:>10.2f} {doc_tokens:>8} {marker:>10}")

    print(f"\nIncluded {len(included_docs)}/{len(retrieved_docs)} documents")
    print(f"Total context: {base_tokens + tokens_used:,} / {MODEL_LIMITS[model]:,} tokens")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 03: Context Window Management (Solution)\n")

    system_prompt = """\
You are a senior Site Reliability Engineer. You help diagnose and resolve
infrastructure incidents. Use specific kubectl, AWS CLI, or other commands
in your responses. Be concise and action-oriented."""

    exercise1_count_and_budget(system_prompt)
    exercise2_conversation_growth(system_prompt)
    exercise3_sliding_window(system_prompt)
    exercise4_budget_aware_rag(system_prompt)

    print("\n" + "=" * 60)
    print("Lab complete! Key takeaways:")
    print("  1. Token count grows fast — system prompt + history + docs all count.")
    print("  2. Sliding window trimming is the standard pattern for long chats.")
    print("  3. Budget-aware RAG ensures you include the most relevant context.")
    print("  4. The model is stateless — YOU manage what fits in the window.")
    print("=" * 60)


if __name__ == "__main__":
    main()
