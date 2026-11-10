#!/usr/bin/env bash
# Phase 2 の kind クラスターを構築する（up.ps1 の Bash 版）。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$REPOSITORY_ROOT"

assert_kind_prerequisites
initialize_kind_cluster "$CLUSTER_NAME" "$LAB_KUBECONFIG" phases/02-kind-basics/cluster.yaml
import_workboard_images "$CLUSTER_NAME"
common=(--kubeconfig "$LAB_KUBECONFIG" --context "$CLUSTER_CONTEXT")
kubectl "${common[@]}" apply -f phases/02-kind-basics/manifests/namespace.yaml
kubectl "${common[@]}" apply -f phases/02-kind-basics/manifests/postgres.yaml
kubectl "${common[@]}" -n workboard rollout status deployment/workboard-postgres --timeout=180s
kubectl "${common[@]}" apply -f phases/02-kind-basics/manifests/migrate.yaml
kubectl "${common[@]}" -n workboard wait --for=condition=complete job/workboard-migrate --timeout=180s
kubectl "${common[@]}" apply -f phases/02-kind-basics/manifests/app.yaml
for deployment in workboard-api workboard-web; do
  kubectl "${common[@]}" -n workboard rollout status "deployment/$deployment" --timeout=180s
done
kubectl "${common[@]}" get nodes
kubectl "${common[@]}" -n workboard get pods,rs,deploy,svc
echo '構築完了。Phase 2 の port-forward 手順で画面を開いてください。'
