#!/usr/bin/env python3
"""
Lab 01: Tokenization — SOLUTION
=================================
Reference implementation. Try to complete lab.py yourself before reading this.
"""

import tiktoken


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_encoder() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def tokenize(enc: tiktoken.Encoding, text: str) -> list[int]:
    return enc.encode(text)


def token_strings(enc: tiktoken.Encoding, token_ids: list[int]) -> list[str]:
    return [enc.decode([tid]) for tid in token_ids]


def count_tokens(enc: tiktoken.Encoding, text: str) -> int:
    return len(enc.encode(text))


def token_cost_usd(token_count: int, price_per_million: float) -> float:
    return (token_count / 1_000_000) * price_per_million


# ── Exercises ─────────────────────────────────────────────────────────────────

def exercise1_basic_tokenization(enc: tiktoken.Encoding) -> None:
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
        print(f"\nCommand: {cmd}")
        print(f"Tokens:  {pieces}")
        print(f"Count:   {len(ids)}")


def exercise2_infrastructure_content(enc: tiktoken.Encoding) -> None:
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

    print(f"\n{'Content Type':<30} {'Tokens':>7} {'Lines':>7} {'Tok/Line':>9}")
    print("─" * 58)
    for name, content in contents.items():
        lines = len(content.strip().split("\n"))
        tokens = count_tokens(enc, content)
        print(f"{name:<30} {tokens:>7} {lines:>7} {tokens/lines:>9.1f}")


def exercise3_cost_estimation(enc: tiktoken.Encoding) -> None:
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

    haiku_input_per_million = 0.25
    haiku_output_per_million = 1.25
    output_tokens_estimate = 300

    sys_tokens = count_tokens(enc, system_prompt)
    log_tokens = count_tokens(enc, log_sample)
    total_input = sys_tokens + log_tokens
    total_output = output_tokens_estimate

    cost_per_call = (
        token_cost_usd(total_input, haiku_input_per_million)
        + token_cost_usd(total_output, haiku_output_per_million)
    )

    print(f"\nSystem prompt:   {sys_tokens:>6} tokens")
    print(f"Log sample:      {log_tokens:>6} tokens")
    print(f"Total input:     {total_input:>6} tokens")
    print(f"Est. output:     {total_output:>6} tokens")
    print(f"Cost per call:   ${cost_per_call:.6f}")
    print("─" * 45)
    for scale, label in [(10, "10 alerts/day"), (100, "100 alerts/day"), (1000, "1000 alerts/day")]:
        daily = cost_per_call * scale
        monthly = daily * 30
        print(f"{label:<18}  ${daily:.4f}/day   ${monthly:.2f}/month")


def exercise4_tokenization_surprises(enc: tiktoken.Encoding) -> None:
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
        print(f"{name:<22} {len(ids):>6}  {pieces}")

    print(
        "\nNotice: dates, IPs, UUIDs, and camelCase words split into many tokens.\n"
        "        A UUID = ~10 tokens; an IP address = ~5 tokens.\n"
        "        'Kubernetes' ≠ 'kubernetes' — case changes the tokenization."
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\nLab 01: Tokenization (Solution)\n")
    enc = get_encoder()

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
