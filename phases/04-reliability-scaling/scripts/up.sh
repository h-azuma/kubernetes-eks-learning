#!/usr/bin/env bash
# Phase 4 の kind クラスターを構築・更新する（up.ps1 の Bash 版）。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$REPOSITORY_ROOT"

assert_kind_prerequisites
initialize_kind_cluster "$CLUSTER_NAME" "$LAB_KUBECONFIG" phases/04-reliability-scaling/cluster.yaml
import_workboard_images "$CLUSTER_NAME"
common=(--kubeconfig "$LAB_KUBECONFIG" --context "$CLUSTER_CONTEXT")
secret_file="$REPOSITORY_ROOT/phases/04-reliability-scaling/kustomize/overlays/kind/secrets/db.env"
if [[ ! -e "$secret_file" ]]; then
  (umask 077; printf 'POSTGRES_PASSWORD=%s\n' "$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')" > "$secret_file")
  echo "ローカル専用の DB パスワードを生成しました（値は表示しません）: $secret_file"
fi
# metrics-server は kube-system に入れる。HPA が CPU を読むために必要。
kubectl "${common[@]}" apply -k phases/04-reliability-scaling/kustomize/metrics-server
# 完了済み Job の spec は変更できない。Alembic は何度実行しても安全なので、毎回削除してから適用する。
kubectl "${common[@]}" -n workboard delete job workboard-migrate --ignore-not-found
kubectl "${common[@]}" apply -k phases/04-reliability-scaling/kustomize/overlays/kind
kubectl "${common[@]}" -n workboard rollout status statefulset/workboard-postgres --timeout=180s
kubectl "${common[@]}" -n workboard wait --for=condition=complete job/workboard-migrate --timeout=300s
for deployment in workboard-api workboard-web; do
  kubectl "${common[@]}" -n workboard rollout status "deployment/$deployment" --timeout=180s
done
kubectl "${common[@]}" -n kube-system rollout status deployment/metrics-server --timeout=180s
kubectl "${common[@]}" wait --for=condition=Available apiservice/v1beta1.metrics.k8s.io --timeout=180s
kubectl "${common[@]}" get nodes
kubectl "${common[@]}" -n workboard get pods,sts,deploy,svc,pvc,hpa,pdb -o wide
echo '構築完了。Phase 4 の port-forward 手順（8082 番）で画面を開いてください。'
