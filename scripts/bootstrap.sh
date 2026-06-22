#!/usr/bin/env bash
set -euo pipefail

required_commands=(aws terraform kubectl docker jq)

echo "Checking required commands..."
for command_name in "${required_commands[@]}"; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    exit 1
  fi
  echo "  ok: $command_name"
done

echo "Checking AWS credentials..."
aws sts get-caller-identity >/tmp/ai-chaos-gameday-aws-identity.json
jq -r '"  account: \(.Account)\n  arn: \(.Arn)"' /tmp/ai-chaos-gameday-aws-identity.json

echo "Checking Docker daemon..."
docker info >/dev/null

echo "Bootstrap checks passed."
