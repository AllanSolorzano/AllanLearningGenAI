# Chaos Mesh Install Notes

Install Chaos Mesh separately so the operator/CRDs are explicit and reviewable:

```bash
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
  --namespace chaos-system \
  --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock
```

The sample experiments in this folder are intentionally not included in `kustomization.yaml`; apply them one at a time during a controlled GameDay.
