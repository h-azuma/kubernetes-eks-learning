#!/usr/bin/env bash
# Phase 8 の kind クラスターを構築・更新する（up.ps1 の Bash 版）。
# Argo CD が同期するリポジトリ: 環境変数 GITOPS_REPO_URL があればその URL、なければこの clone の origin。
# リビジョン: 環境変数 GITOPS_REVISION があればその値、なければ今のブランチ。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
cd "$REPOSITORY_ROOT"

gitops_repo_url() {
  local url="${GITOPS_REPO_URL:-}"
  [[ -n "$url" ]] || url=$(git -C "$REPOSITORY_ROOT" remote get-url origin) || true
  [[ -n "$url" ]] || die 'Argo CD が同期するリポジトリの URL が分かりません。環境変数 GITOPS_REPO_URL に、自分が push できる公開リポジトリの HTTPS の URL を設定してください。'
  # SSH 形式は鍵が要るため公開リポジトリの HTTPS に直し、URL に含まれる認証情報は取り除く。
  sed -E -e 's#^(ssh://)?git@([^:/]+)[:/]#https://\2/#' -e 's#^https://[^@/]+@#https://#' <<<"$url"
}

gitops_revision() {
  local revision="${GITOPS_REVISION:-}"
  [[ -n "$revision" ]] || revision=$(git -C "$REPOSITORY_ROOT" rev-parse --abbrev-ref HEAD) || true
  [[ -n "$revision" && "$revision" != HEAD ]] || die '同期するブランチが分かりません。環境変数 GITOPS_REVISION にブランチまたはタグを設定してください。'
  printf '%s\n' "$revision"
}

assert_kind_prerequisites
initialize_kind_cluster "$CLUSTER_NAME" "$LAB_KUBECONFIG" phases/08-devops-observability/cluster.yaml
import_workboard_images "$CLUSTER_NAME"
common=(--kubeconfig "$LAB_KUBECONFIG" --context "$CLUSTER_CONTEXT")
phase=phases/08-devops-observability
secret_file="$REPOSITORY_ROOT/$phase/kustomize/overlays/kind/secrets/db.env"
if [[ ! -e "$secret_file" ]]; then
  (umask 077; printf 'POSTGRES_PASSWORD=%s\n' "$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')" > "$secret_file")
  echo "ローカル専用の DB パスワードを生成しました（値は表示しません）: $secret_file"
fi
# kubectl create --dry-run の出力を apply して、既にあるリソースでも失敗しないようにする。
apply_generated() {
  kubectl "${common[@]}" "$@" --dry-run=client -o yaml | kubectl "${common[@]}" apply -f -
}
# Secret は Git に入れられないため、Argo CD の同期対象には含めず、ここで作る（decisions/0015）。
apply_generated create namespace workboard
apply_generated -n workboard create secret generic workboard-db --from-env-file="$secret_file"
# 完了済み Job の spec は変更できない。Alembic は何度実行しても安全なので、毎回削除してから適用する。
kubectl "${common[@]}" -n workboard delete job workboard-migrate --ignore-not-found
kubectl "${common[@]}" apply -k "$phase/kustomize/overlays/kind"

apply_generated create namespace argocd
# CRD が大きく client-side apply の annotation 上限を超えるため、server-side apply を使う。
kubectl "${common[@]}" apply -n argocd --server-side --force-conflicts -f "$ARGOCD_INSTALL_URL"
kubectl "${common[@]}" apply -k "$phase/kustomize/monitoring"

kubectl "${common[@]}" -n workboard rollout status statefulset/workboard-postgres --timeout=180s
kubectl "${common[@]}" -n workboard wait --for=condition=complete job/workboard-migrate --timeout=300s
for deployment in workboard-api workboard-web; do
  kubectl "${common[@]}" -n workboard rollout status "deployment/$deployment" --timeout=180s
done
kubectl "${common[@]}" -n monitoring rollout status deployment/prometheus --timeout=180s
kubectl "${common[@]}" -n argocd rollout status statefulset/argocd-application-controller --timeout=300s
kubectl "${common[@]}" -n argocd wait --for=condition=Available deployment --all --timeout=300s
kubectl "${common[@]}" wait --for=condition=Established crd/applications.argoproj.io --timeout=60s

repo_url=$(gitops_repo_url)
revision=$(gitops_revision)
echo "Argo CD の同期対象: $repo_url（$revision）"
kubectl "${common[@]}" apply -f "$phase/argocd/application.yaml"
kubectl "${common[@]}" -n argocd patch application workboard --type merge -p "{\"spec\":{\"source\":{\"repoURL\":\"$repo_url\",\"targetRevision\":\"$revision\"}}}"
kubectl "${common[@]}" get nodes
kubectl "${common[@]}" -n workboard get pods,sts,deploy,svc,pvc,pdb -o wide
kubectl "${common[@]}" -n monitoring get pods
kubectl "${common[@]}" -n argocd get pods,application
echo '構築完了。Phase 8 の port-forward 手順（WorkBoard 8084、Argo CD 8085、Prometheus 8087）で画面を開いてください。'
echo 'Application は Git に push 済みのリビジョンだけを同期できます。README の「検証コマンド・期待結果」の 5・6 の手順を確認してください。'
