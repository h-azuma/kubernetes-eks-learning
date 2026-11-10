#!/usr/bin/env bash
# Phase 5 の kind クラスターを構築・更新する（up.ps1 の Bash 版）。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$REPOSITORY_ROOT"
CALICO_MANIFEST='https://raw.githubusercontent.com/projectcalico/calico/v3.33.0/manifests/calico.yaml'

assert_kind_prerequisites
# 既定の CNI を無効にした kind は、CNI を入れるまで Node が Ready にならないため、--wait なしで作成する。
initialize_kind_cluster "$CLUSTER_NAME" "$LAB_KUBECONFIG" phases/05-security-and-failure/cluster.yaml ''
common=(--kubeconfig "$LAB_KUBECONFIG" --context "$CLUSTER_CONTEXT")
# 存在しない名前の get は stderr に出力して停止するため、ラベル検索の出力が空かどうかで判定する。
if [[ -z "$(kubectl "${common[@]}" -n kube-system get daemonset -l k8s-app=calico-node -o name)" ]]; then
  # CRD が大きく apply だと上限を超えることがあるため、公式手順どおり create を使う。
  kubectl "${common[@]}" create -f "$CALICO_MANIFEST"
fi
kubectl "${common[@]}" -n kube-system rollout status daemonset/calico-node --timeout=300s
kubectl "${common[@]}" -n kube-system rollout status deployment/calico-kube-controllers --timeout=300s
kubectl "${common[@]}" wait --for=condition=Ready node --all --timeout=180s
kubectl "${common[@]}" -n kube-system rollout status deployment/coredns --timeout=180s
import_workboard_images "$CLUSTER_NAME"
secret_file="$REPOSITORY_ROOT/phases/05-security-and-failure/kustomize/overlays/kind/secrets/db.env"
if [[ ! -e "$secret_file" ]]; then
  (umask 077; printf 'POSTGRES_PASSWORD=%s\n' "$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')" > "$secret_file")
  echo "ローカル専用の DB パスワードを生成しました（値は表示しません）: $secret_file"
fi
# 完了済み Job の spec は変更できない。Alembic は何度実行しても安全なので、毎回削除してから適用する。
# 初回は Namespace が無いが、--ignore-not-found により Job の削除はエラーにならない。
kubectl "${common[@]}" -n workboard delete job workboard-migrate --ignore-not-found
kubectl "${common[@]}" apply -k phases/05-security-and-failure/kustomize/overlays/kind
kubectl "${common[@]}" -n workboard rollout status statefulset/workboard-postgres --timeout=180s
kubectl "${common[@]}" -n workboard wait --for=condition=complete job/workboard-migrate --timeout=300s
for deployment in workboard-api workboard-web; do
  kubectl "${common[@]}" -n workboard rollout status "deployment/$deployment" --timeout=180s
done
kubectl "${common[@]}" get nodes
kubectl "${common[@]}" -n workboard get pods,sts,deploy,svc,sa,networkpolicy
echo '構築完了。Phase 5 の port-forward 手順（8083 番）で画面を開いてください。'
