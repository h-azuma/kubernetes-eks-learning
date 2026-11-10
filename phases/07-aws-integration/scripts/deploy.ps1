#Requires -Version 5.1
# eks overlay を EKS へ適用する。承認済みの AWS 環境でだけ手で実行する。
# ダミーのレジストリ・RDS エンドポイント・許可 CIDR を、確認した実際の値に置き換えて適用する。
# 事前に write-db-secret を実行し、環境変数 WORKBOARD_ALLOWED_CIDR（例: 自分の IP/32）を設定する。
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"

$allowedCidr = $env:WORKBOARD_ALLOWED_CIDR
if ($allowedCidr -notmatch '^\d{1,3}(\.\d{1,3}){3}/([0-9]|[12][0-9]|3[0-2])$' -or $allowedCidr.StartsWith('0.0.0.0/')) {
    throw 'WORKBOARD_ALLOWED_CIDR に、公開を許可する自分の IP の CIDR（例: 198.51.100.7/32）を設定してください。0.0.0.0/0 は不可。'
}
$overlay = 'phases/07-aws-integration/kustomize/overlays/eks'
if (-not (Test-Path (Join-Path $RepositoryRoot "$overlay/secrets/db.env"))) { throw '先に write-db-secret を実行してください。' }
$accountId = Confirm-AwsTarget
$registry = "$accountId.dkr.ecr.$Region.amazonaws.com"
$rdsHost = Get-TerraformOutput 'db_endpoint_address'
$common = @('--kubeconfig', $LabKubeconfig, '--context', "arn:aws:eks:${Region}:${accountId}:cluster/$ClusterName")
Push-Location $RepositoryRoot
try {
    # 完了済み Job の spec は変更できない。Alembic は何度実行しても安全なので、毎回削除してから適用する。
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'delete', 'job', 'workboard-migrate', '--ignore-not-found'))
    $manifest = & kubectl kustomize $overlay
    if ($LASTEXITCODE -ne 0) { throw 'kubectl kustomize に失敗しました。' }
    ($manifest -join "`n").Replace('111122223333.dkr.ecr.ap-northeast-1.amazonaws.com', $registry).Replace('workboard-learning-db.example.ap-northeast-1.rds.amazonaws.com', $rdsHost).Replace('203.0.113.10/32', $allowedCidr) | kubectl @common apply -f -
    if ($LASTEXITCODE -ne 0) { throw 'kubectl apply に失敗しました。' }
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'wait', '--for=condition=complete', 'job/workboard-migrate', '--timeout=300s'))
    foreach ($deployment in @('workboard-api', 'workboard-web')) {
        Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', "deployment/$deployment", '--timeout=180s'))
    }
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'get', 'pods,deploy,svc,ingress'))
    Write-Output 'ALB が作成されるまで数分かかります。kubectl get ingress の ADDRESS を README の手順で確認してください。'
}
finally { Pop-Location }
