#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="/tmp/k8s-diff-$(date +%s).txt"

echo "Diff report: $OUT"

sanitize_cmd() {
  if command -v yq >/dev/null 2>&1; then
    # Use mikefarah yq v4+ syntax
    yq eval 'del(.metadata.creationTimestamp, .metadata.resourceVersion, .metadata.uid, .metadata.managedFields, .metadata.generation, .metadata.selfLink, .status, .metadata.annotations."kubectl.kubernetes.io/last-applied-configuration")' -
  else
    # Best-effort fallback: strip common mutable metadata and status
    sed -E '/^\s*creationTimestamp:|^\s*resourceVersion:|^\s*uid:|^\s*generation:|^\s*selfLink:|^\s*managedFields:|^\s*annotations:\s*$/d' | sed '/^status:/,$d'
  fi
}

compare() {
  local repo_file="$1"
  local kubectl_cmd="$2"
  echo "==== $repo_file ====" >> "$OUT"
  if [ -f "$REPO_ROOT/$repo_file" ]; then
    local cluster_yaml
    if ! cluster_yaml="$(eval "$kubectl_cmd" 2>/dev/null || true)"; then
      echo "Cluster fetch failed: $kubectl_cmd" >> "$OUT"
      echo >> "$OUT"
      return
    fi
    if [ -z "$cluster_yaml" ]; then
      echo "Cluster resource not found: $kubectl_cmd" >> "$OUT"
      echo >> "$OUT"
      return
    fi
    printf '%s' "$cluster_yaml" | sanitize_cmd > /tmp/cluster.yaml
    sanitize_cmd < "$REPO_ROOT/$repo_file" > /tmp/repo.yaml
    if diff -u /tmp/repo.yaml /tmp/cluster.yaml >> "$OUT"; then
      echo "(no differences)" >> "$OUT"
    else
      true
    fi
  else
    echo "Repo file not found: $REPO_ROOT/$repo_file" >> "$OUT"
  fi
  echo >> "$OUT"
}

# Run comparisons
compare "monitoring/argo-servicemonitor.yaml" "kubectl -n monitoring get servicemonitor argo-servicemonitor -o yaml"
compare "monitoring/mlflow-exporter-servicemonitor.yaml" "kubectl -n monitoring get servicemonitor mlflow-exporter -o yaml"
compare "monitoring/mlflow-exporter-service.yaml" "kubectl -n mlflow get svc mlflow-exporter -o yaml"
compare "monitoring/mlflow-exporter-deployment.yaml" "kubectl -n mlflow get deploy mlflow-exporter -o yaml"

# Prometheus CR (cluster only)
echo "==== Prometheus CR (cluster) ====" >> "$OUT"
if kubectl -n monitoring get prometheus kube-prometheus-stack-prometheus -o yaml >/tmp/prom_cr.yaml 2>/dev/null; then
  sanitize_cmd < /tmp/prom_cr.yaml >> "$OUT"
else
  echo "Prometheus CR kube-prometheus-stack-prometheus not found in monitoring namespace" >> "$OUT"
fi

echo "Report written to $OUT"
cat "$OUT"

exit 0
