# Dynatrace Operator Install Notes

The GitOps application for this folder is manual by default and only applies the namespace. Install the Dynatrace Operator and apply the example secret/DynaKube after you provide real tenant values.

Typical flow:

```bash
kubectl apply -f k8s/dynatrace/namespace.yaml
kubectl -n dynatrace create secret generic dynakube \
  --from-literal=apiToken="$DYNATRACE_API_TOKEN" \
  --from-literal=dataIngestToken="$DYNATRACE_DATA_INGEST_TOKEN"

# Install the operator with the method currently recommended in Dynatrace docs.
# Then copy dynakube.example.yaml, replace apiUrl, and apply it:
kubectl apply -f k8s/dynatrace/dynakube.example.yaml
```

Keep the real secret outside Git. The `chaos-app` namespace is labeled for selective injection.
