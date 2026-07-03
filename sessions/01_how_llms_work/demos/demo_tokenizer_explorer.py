#!/usr/bin/env python3
"""
Demo: Tokenizer Explorer
=========================
Run this to interactively explore how text gets tokenized.
Type any text and see exactly how it splits into tokens.

No API key required. Runs entirely offline.

Usage:
    python demo_tokenizer_explorer.py
    python demo_tokenizer_explorer.py --batch    # Run preset examples only
"""

import sys
import tiktoken


ENCODER = tiktoken.get_encoding("cl100k_base")

# Pricing reference (approximate, as of 2024)
PRICING = {
    "Claude Haiku (input)":   0.25,
    "Claude Haiku (output)":  1.25,
    "Claude Sonnet (input)":  3.00,
    "Claude Sonnet (output)": 15.00,
    "GPT-4o (input)":         5.00,
    "GPT-4o (output)":        15.00,
}


def tokenize_and_display(text: str, label: str = "") -> int:
    """Tokenize text and display a visual breakdown. Returns token count."""
    token_ids = ENCODER.encode(text)
    token_strs = [ENCODER.decode([tid]) for tid in token_ids]
    count = len(token_ids)

    # Build colored token display (alternating visual groups)
    # Using simple brackets for terminal compatibility
    token_display = " | ".join(repr(t) for t in token_strs)

    if label:
        print(f"\n{'─' * 60}")
        print(f"  {label}")
        print(f"{'─' * 60}")
    else:
        print(f"\n{'─' * 60}")

    # Truncate long texts for display
    display_text = text if len(text) <= 80 else text[:77] + "..."
    print(f"  Text:    {repr(display_text)}")
    print(f"  Tokens:  {token_display}")
    print(f"  Count:   {count} tokens  |  {len(text)} chars  |  ~{len(text.split())} words")

    # Cost estimates
    costs = []
    for model, price in list(PRICING.items())[:4]:  # Show first 4
        cost = (count / 1_000_000) * price
        costs.append(f"{model}: ${cost:.6f}")
    print(f"  Cost:    {' | '.join(costs[:2])}")
    print(f"           {' | '.join(costs[2:4])}")

    return count


def run_preset_examples() -> None:
    """Run a curated set of examples that show interesting tokenization behavior."""

    print("\n" + "=" * 60)
    print("  TOKENIZER EXPLORER — Preset Examples")
    print("  Tokenizer: cl100k_base (GPT-4 / similar models)")
    print("=" * 60)

    # ── Section 1: DevOps commands ─────────────────────────────────────
    print("\n\n[1] DevOps Commands")

    commands = {
        "kubectl get":         "kubectl get pods --namespace production --output json",
        "terraform":           "terraform plan -out=tfplan -var-file=prod.tfvars",
        "docker build":        "docker build --no-cache -t myapp:v2.1.0 --build-arg ENV=prod .",
        "helm upgrade":        "helm upgrade --install nginx-ingress ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace",
        "aws cli":             "aws ec2 describe-instances --region us-east-1 --filters 'Name=tag:Environment,Values=production' --query 'Reservations[].Instances[].InstanceId'",
    }
    for label, cmd in commands.items():
        tokenize_and_display(cmd, label)

    # ── Section 2: Infrastructure config ──────────────────────────────
    print("\n\n[2] Infrastructure Config vs Plain English")

    dockerfile = 'FROM python:3.11-slim\nWORKDIR /app\nRUN pip install -r requirements.txt\nCMD ["python", "app.py"]'
    prose = "This builds a Python 3.11 container image, sets the working directory, installs dependencies, and runs the app."
    tokenize_and_display(dockerfile, "Dockerfile (4 lines)")
    tokenize_and_display(prose, "Same info as plain English")

    # ── Section 3: Tokenization surprises ─────────────────────────────
    print("\n\n[3] Tokenization Surprises")

    surprises = {
        "UUID":              "550e8400-e29b-41d4-a716-446655440000",
        "IPv4 address":      "192.168.10.100",
        "ISO date":          "2024-10-15T14:23:01Z",
        "CamelCase error":   "CrashLoopBackOff",
        "SCREAMING_SNAKE":   "DATABASE_CONNECTION_POOL_MAX_SIZE",
        "Semver":            "nginx:1.24.0-alpine",
        "AWS resource ID":   "arn:aws:iam::123456789012:role/ProductionEKSRole",
    }
    for label, text in surprises.items():
        tokenize_and_display(text, label)

    # ── Section 4: Scale matters ───────────────────────────────────────
    print("\n\n[4] Scale — How Fast Tokens Add Up")
    print("\n  Scenario: Log analysis tool")

    log_line = "2024-10-15 14:23:01 ERROR [auth-service] [req-id:abc-123] Connection pool exhausted: 20/20 connections in use"
    per_line = len(ENCODER.encode(log_line))
    print(f"\n  Per log line: {per_line} tokens")
    print(f"  1,000 lines:  {per_line * 1_000:,} tokens  (~${(per_line * 1_000 / 1_000_000) * 3.0:.4f} Sonnet input)")
    print(f"  10,000 lines: {per_line * 10_000:,} tokens  (~${(per_line * 10_000 / 1_000_000) * 3.0:.4f} Sonnet input)")
    print(f"  Context window (200K): fits {200_000 // per_line:,} log lines at a time")

    # ── Section 5: Context window comparison ──────────────────────────
    print("\n\n[5] Context Window Reference")
    print()
    models = [
        ("GPT-3.5 Turbo",    16_384),
        ("GPT-4o",          128_000),
        ("Claude Haiku",    200_000),
        ("Claude Sonnet",   200_000),
        ("llama-3-8b",        8_192),
    ]
    per_word = 1.3  # tokens per English word
    print(f"  {'Model':<22} {'Context':>10} {'~Words':>10} {'~Pages':>8}")
    print("  " + "─" * 56)
    for name, ctx in models:
        words = int(ctx / per_word)
        pages = words // 250
        print(f"  {name:<22} {ctx:>10,} {words:>10,} {pages:>8,}")


def run_interactive() -> None:
    """Interactive mode — let the user type any text."""
    print("\n" + "=" * 60)
    print("  TOKENIZER EXPLORER — Interactive Mode")
    print("  Type any text to see its token breakdown.")
    print("  Press Ctrl+C or type 'quit' to exit.")
    print("=" * 60)

    while True:
        try:
            text = input("\nEnter text: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break

        if text.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        if not text:
            continue

        tokenize_and_display(text)


def main() -> None:
    batch_mode = "--batch" in sys.argv

    # Always show preset examples
    run_preset_examples()

    if not batch_mode:
        print("\n" + "=" * 60)
        print("  Presets complete. Entering interactive mode...")
        print("=" * 60)
        run_interactive()
    else:
        print("\n\nBatch mode — exiting after presets.")


if __name__ == "__main__":
    main()
