#!/usr/bin/env bash
set -euo pipefail

echo "Creating argocd namespace..."
kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -

echo "Installing Argo CD official manifests..."
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

echo "Waiting for Argo CD deployments..."
kubectl -n argocd wait --for=condition=available deployment --all --timeout=600s

echo "Argo CD installed."
echo "Port-forward UI with: kubectl -n argocd port-forward svc/argocd-server 8081:443"
