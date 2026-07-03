"""Sample DevOps runbook corpus for Session 07 labs and demos."""

from __future__ import annotations

# Simulated multi-page documents (as if extracted from PDFs).
DOCUMENTS: list[dict] = [
    {
        "doc_id": "RB-K8S-001",
        "title": "Kubernetes Pod Failures",
        "source": "runbooks/k8s-pod-failures.md",
        "service": "kubernetes",
        "environment": "production",
        "owner": "platform-sre",
        "version": "3.2",
        "pages": [
            {
                "page": 1,
                "heading": "CrashLoopBackOff",
                "text": (
                    "A pod in CrashLoopBackOff restarts repeatedly. "
                    "Run kubectl logs <pod> --previous for the prior crash. "
                    "Common causes: application panic, missing ConfigMap, wrong command, or OOMKilled."
                ),
            },
            {
                "page": 2,
                "heading": "OOMKilled",
                "text": (
                    "Exit code 137 indicates the kernel killed the container for memory. "
                    "Inspect kubectl describe pod for OOMKilled. "
                    "Raise memory limits or fix leaks; check cgroup metrics in Prometheus."
                ),
            },
            {
                "page": 3,
                "heading": "ImagePullBackOff",
                "text": (
                    "Kubernetes cannot pull the image. Verify tag, registry auth, and imagePullSecrets. "
                    "Test with docker pull or crane pull from a bastion with the same credentials."
                ),
            },
        ],
    },
    {
        "doc_id": "RB-NET-002",
        "title": "Ingress and Upstream Health",
        "source": "runbooks/ingress-upstream.md",
        "service": "nginx-ingress",
        "environment": "production",
        "owner": "networking",
        "version": "1.8",
        "pages": [
            {
                "page": 1,
                "heading": "502 Bad Gateway",
                "text": (
                    "502 means the ingress cannot reach a healthy upstream. "
                    "Confirm backend pods pass readiness probes. "
                    "Check ingress controller logs and upstream connection timeouts."
                ),
            },
            {
                "page": 2,
                "heading": "Certificate expiry",
                "text": (
                    "Expired TLS certificates break HTTPS. "
                    "Use cert-manager describe certificate or openssl s_client to inspect notAfter. "
                    "Renew via ACME or update the Kubernetes tls secret."
                ),
            },
        ],
    },
    {
        "doc_id": "RB-IAC-003",
        "title": "Terraform Operations",
        "source": "runbooks/terraform-ops.md",
        "service": "terraform",
        "environment": "shared",
        "owner": "platform-eng",
        "version": "2.0",
        "pages": [
            {
                "page": 1,
                "heading": "State lock",
                "text": (
                    "Terraform state lock prevents concurrent applies. "
                    "Only terraform force-unlock <LOCK_ID> when no other process holds the lock. "
                    "Check CI job history before unlocking."
                ),
            },
            {
                "page": 2,
                "heading": "Drift detection",
                "text": (
                    "Run terraform plan in read-only mode to detect drift. "
                    "Import or apply carefully; document manual console changes in the change ticket."
                ),
            },
        ],
    },
    {
        "doc_id": "RB-DB-004",
        "title": "PostgreSQL Incidents",
        "source": "runbooks/postgres-incidents.md",
        "service": "postgresql",
        "environment": "production",
        "owner": "data-platform",
        "version": "4.1",
        "pages": [
            {
                "page": 1,
                "heading": "Connection pool exhausted",
                "text": (
                    "Applications cannot acquire connections when the pool is saturated. "
                    "Inspect pg_stat_activity and max_connections. "
                    "Short term: raise pool size; long term: deploy PgBouncer."
                ),
            },
            {
                "page": 2,
                "heading": "Slow queries",
                "text": (
                    "Long-running queries block others. "
                    "Use EXPLAIN ANALYZE, check missing indexes, and review autovacuum lag on hot tables."
                ),
            },
        ],
    },
    {
        "doc_id": "RB-AWS-005",
        "title": "AWS Access and Storage",
        "source": "runbooks/aws-access.md",
        "service": "aws",
        "environment": "production",
        "owner": "cloud-sre",
        "version": "1.5",
        "pages": [
            {
                "page": 1,
                "heading": "S3 Access Denied",
                "text": (
                    "Access denied usually means IAM or bucket policy mismatch. "
                    "Confirm role on the pod service account with aws sts get-caller-identity. "
                    "Verify bucket policy does not explicitly deny the principal."
                ),
            },
        ],
    },
]
