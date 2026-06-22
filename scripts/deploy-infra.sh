#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR/terraform"

echo "Initializing Terraform..."
terraform init

echo "Planning infrastructure..."
terraform plan -out=tfplan

echo "Applying infrastructure..."
terraform apply tfplan

CLUSTER_NAME="$(terraform output -raw cluster_name)"
REGION="$(terraform output -raw region)"

echo "Updating kubeconfig for ${CLUSTER_NAME} in ${REGION}..."
aws eks update-kubeconfig --region "$REGION" --name "$CLUSTER_NAME"

echo "Infrastructure deployed."
