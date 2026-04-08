#!/usr/bin/env python3
"""
Lab 01: Tokenization — How LLMs See Text
==========================================
LLMs don't process raw text — they process token IDs. In this lab you'll
explore how text gets tokenized, measure token counts for real infrastructure
content, and build a cost estimator.

No API key required. Run entirely offline.

Prerequisites:
    pip install tiktoken

Run:
    python lab.py

When stuck: check solution.py
"""

import tiktoken


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_encoder() -> tiktoken.Encoding:
    """Return the cl100k_base encoder (used by GPT-4 and similar models).

    This is a standard reference tokenizer. Anthropic uses its own tokenizer,
    but cl100k_base gives you accurate intuition for how tokenization works.
    """
    # TODO 1: Create and return the cl100k_base encoder.
    # Hint: tiktoken.get_encoding("cl100k_base")
    pass


def tokenize(enc: tiktoken.Encoding, text: str) -> list[int]:
    """Encode text and return the list of token IDs."""
    # TODO 2: Encode the text and return the token ID list.
    # Hint: enc.encode(text)
    pass


def token_strings(enc: tiktoken.Encoding, token_ids: list[int]) -> list[str]:
    """Decode each token ID individually to see what string it represents.

    This shows you *how* the tokenizer split the text — each element is
    the string representation of one token.
    """
    # TODO 3: Return a list where each element is enc.decode([one_token_id]).
    # Hint: [enc.decode([tid]) for tid in token_ids]
    pass


def count_tokens(enc: tiktoken.Encoding, text: str) -> int:
    """Return the number of tokens in the text."""
    # TODO 4: Return the token count.
    # Hint: len(enc.encode(text))
    pass


def token_cost_usd(token_count: int, price_per_million: float) -> float:
    """Estimate cost in USD for a given token count and price per million tokens.

    Example prices (approximate, as of 2024):
        Claude Haiku input:  $0.25 / 1M tokens
        Claude Haiku output: $1.25 / 1M tokens
        Claude Sonnet input: $3.00 / 1M tokens
        Claude Sonnet output:$15.00 / 1M tokens
    """
    # TODO 5: Calculate and return cost in USD.
    # Formula: (token_count / 1_000_000) * price_per_million
    pass


# ── Exercises ─────────────────────────────────────────────────────────────────

def exercise1_basic_tokenization(enc: tiktoken.Encoding) -> None:
    """Exercise 1: Tokenize a command and inspect the result.

    Expected insight: common DevOps terms may split in surprising ways.
    "kubectl" is NOT a single token — it's two: "kube" + "ctl".
    """
    print("=" * 60)
    print("Exercise 1: Basic Tokenization")
    print("=" * 60)

    commands = [
        "kubectl get pods --namespace production",
        "terraform plan -out=tfplan",
        "docker build -t myapp:latest .",
        "helm upgrade --install myapp ./chart --set replicas=3",
    ]

    for cmd in commands:
        ids = tokenize(enc, cmd)
        pieces = token_strings(enc, ids)

        # TODO 6: Print the command, its token strings (pieces), and token count.
        # Format example:
        #   Command: kubectl get pods --namespace production
        #   Tokens:  ['kube', 'ctl', ' get', ' pods', ' --', 'names', 'pace', ' production']
        #   Count:   8
        print()


def exercise2_infrastructure_content(enc: tiktoken.Encoding) -> None:
    """Exercise 2: Compare token density across different content types.

    Expected insight: code/config files are much more token-dense than
    English prose. This directly affects cost when building tools that
    process infrastructure files.
    """
    print("\n" + "=" * 60)
    print("Exercise 2: Token Density Across Content Types")
    print("=" * 60)

    dockerfile = """\
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["python", "app.py"]"""

    k8s_deployment = """\
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  namespace: production
  labels:
    app: api-server
    version: v2.1.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      containers:
      - name: api-server
        image: myregistry/api-server:v2.1.0
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "512Mi""""

    terraform_snippet = """\
resource "aws_instance" "web" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.medium"
  subnet_id     = aws_subnet.public.id

  tags = {
    Name        = "web-server"
    Environment = "production"
    Team        = "platform"
    CostCenter  = "engineering"
  }

  lifecycle {
    create_before_destroy = true
  }
}"""

    english_prose = """\
This Terraform configuration creates an AWS EC2 instance with a medium-sized
virtual machine. The instance uses a standard Amazon Linux image and is placed
in the public subnet. It is tagged for cost allocation and ownership tracking,
and uses a lifecycle rule to ensure zero-downtime replacements during updates."""

    python_code = """\
def check_pod_health(namespace: str, app_label: str) -> dict:
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(
        namespace=namespace,
        label_selector=f"app={app_label}"
    )
    healthy = sum(
        1 for pod in pods.items
        if pod.status.phase == "Running"
        and all(c.ready for c in pod.status.container_statuses or [])
    )
    return {"total": len(pods.items), "healthy": healthy}"""

    contents = {
        "Dockerfile (7 lines)":        dockerfile,
        "K8s Deployment (30 lines)":   k8s_deployment,
        "Terraform HCL (20 lines)":    terraform_snippet,
        "English prose (4 lines)":     english_prose,
        "Python code (14 lines)":      python_code,
    }

    # TODO 7: For each content type, compute and print:
    #   - Name, token count, line count, tokens/line ratio
    # Format as a table. Example:
    #   Content Type               Tokens   Lines  Tok/Line
    #   ──────────────────────────────────────────────────
    #   Dockerfile (7 lines)          62       7       8.9
    print(f"\n{'Content Type':<30} {'Tokens':>7} {'Lines':>7} {'Tok/Line':>9}")
    print("─" * 58)
    for name, content in contents.items():
        lines = len(content.strip().split("\n"))
        tokens = count_tokens(enc, content)
        # TODO: print the row
        pass


def exercise3_cost_estimation(enc: tiktoken.Encoding) -> None:
    """Exercise 3: Estimate API costs for a log analysis tool.

    Scenario: You're building an AI-powered log analysis service. Each alert
    triggers an API call with recent log lines + a system prompt. What does
    this cost at different scales?
    """
    print("\n" + "=" * 60)
    print("Exercise 3: Log Analysis Cost Estimation")
    print("=" * 60)

    system_prompt = """\
You are a senior SRE analyzing application logs. Identify the root cause,
affected components, and recommended immediate actions. Be concise."""

    log_sample = """\
2024-10-15 14:23:01.123 ERROR [auth-service] [req-id:abc123] Failed to acquire DB connection: pool exhausted (size=20, waiting=47)
2024-10-15 14:23:01.456 ERROR [auth-service] [req-id:def456] Failed to acquire DB connection: pool exhausted (size=20, waiting=51)
2024-10-15 14:23:01.789 WARN  [auth-service] Connection pool wait time exceeded threshold: 2847ms > 2000ms threshold
2024-10-15 14:23:02.012 ERROR [auth-service] [req-id:ghi789] Authentication failed: database unavailable
2024-10-15 14:23:02.234 ERROR [api-gateway] Upstream auth-service returned 503: Service Unavailable
2024-10-15 14:23:02.456 ERROR [api-gateway] Circuit breaker OPEN for auth-service after 5 consecutive failures
2024-10-15 14:23:03.000 CRIT  [alertmanager] FIRING: AuthServiceDown - auth-service error rate 94% (threshold: 10%)
2024-10-15 14:23:03.123 ERROR [payment-svc] Cannot process payment: auth service unavailable"""

    # Claude Haiku pricing (fast, cheap — good for automated alerting)
    haiku_input_per_million = 0.25
    haiku_output_per_million = 1.25

    # TODO 8: Calculate and print the following:
    #   a) Token count for system_prompt
    #   b) Token count for log_sample
    #   c) Total input tokens (system_prompt + log_sample)
    #   d) Estimated output tokens (assume 300 tokens for the analysis)
    #   e) Cost per API call using Haiku pricing
    #   f) Cost per day at: 10 alerts/day, 100 alerts/day, 1000 alerts/day

    output_tokens_estimate = 300

    # Print a summary like:
    #   System prompt:   187 tokens
    #   Log sample:      312 tokens
    #   Total input:     499 tokens
    #   Est. output:     300 tokens
    #   Cost per call:   $0.000498
    #   ─────────────────────────────────
    #   10 alerts/day:   $0.005 / $0.15 per month
    #   100 alerts/day:  $0.050 / $1.50 per month
    #   1000 alerts/day: $0.498 / $14.94 per month


def exercise4_tokenization_surprises(enc: tiktoken.Encoding) -> None:
    """Exercise 4: Discover tokenization surprises.

    These are common patterns in DevOps content that tokenize unexpectedly.
    Understanding these prevents off-by-one errors in context budgeting.
    """
    print("\n" + "=" * 60)
    print("Exercise 4: Tokenization Surprises")
    print("=" * 60)

    surprises = [
        ("ISO date",          "2024-10-15"),
        ("Compact date",      "20241015"),
        ("IPv4 address",      "192.168.1.100"),
        ("IPv4 (compact)",    "192168001100"),
        ("UUID",              "550e8400-e29b-41d4-a716-446655440000"),
        ("K8s error name",    "CrashLoopBackOff"),
        ("AWS resource ID",   "i-0abc123def456789a"),
        ("Image tag",         "nginx:1.24.0"),
        ("Env var name",      "DATABASE_CONNECTION_POOL_SIZE"),
        ("Cased variants",    "Kubernetes"),
        ("Lower variant",     "kubernetes"),
        ("Space prefix",      " kubernetes"),
    ]

    print(f"\n{'Name':<22} {'Count':>6}  Tokens")
    print("─" * 60)
    for name, text in surprises:
        ids = tokenize(enc, text)
        pieces = token_strings(enc, ids)
        # TODO 9: Print each row.
        # Format: name, token count, list of token strings
        pass

    print(
        "\nNotice: dates, IPs, UUIDs, and camelCase words split into many tokens.\n"
        "        A UUID = ~10 tokens; an IP address = ~5 tokens.\n"
        "        'Kubernetes' ≠ 'kubernetes' — case changes the tokenization."
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 01: Tokenization\n")
    enc = get_encoder()

    if enc is None:
        print("ERROR: get_encoder() returned None. Complete TODO 1 first.")
        return

    exercise1_basic_tokenization(enc)
    exercise2_infrastructure_content(enc)
    exercise3_cost_estimation(enc)
    exercise4_tokenization_surprises(enc)

    print("\n" + "=" * 60)
    print("Lab complete! Key takeaways:")
    print("  1. Tokens ≠ words. Code is 3–5× denser than prose.")
    print("  2. Token count = cost. Measure before assuming.")
    print("  3. Tokenization is model-specific and sometimes surprising.")
    print("=" * 60)


if __name__ == "__main__":
    main()
