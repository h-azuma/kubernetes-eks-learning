#Requires -Version 5.1
# eks overlay を EKS へ適用する。承認済みの AWS 環境でだけ手で実行する。
# overlay のダミーのレジストリ（111122223333...）を、確認したアカウントの ECR に置き換えて適用する。
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
$accountId = Confirm-AwsTarget
$registry = "$accountId.dkr.ecr.$Region.amazonaws.com"
$placeholderRegistry = '111122223333.dkr.ecr.ap-northeast-1.amazonaws.com'
$context = "arn:aws:eks:${Region}:${accountId}:cluster/$ClusterName"
$common = @('--kubeconfig', $LabKubeconfig, '--context', $context)
$overlay = 'phases/06-eks-foundation/kustomize/overlays/eks'
Push-Location $RepositoryRoot
try {
    $secretFile = Join-Path $RepositoryRoot "$overlay/secrets/db.env"
    if (-not (Test-Path $secretFile)) {
        $bytes = New-Object byte[] 24
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $password = -join ($bytes | ForEach-Object { $_.ToString('x2') })
        [IO.File]::WriteAllText($secretFile, "POSTGRES_PASSWORD=$password`n", (New-Object Text.UTF8Encoding $false))
        Write-Output "ローカル専用の DB パスワードを生成しました（値は表示しません）: $secretFile"
    }
    # 完了済み Job の spec は変更できない。Alembic は何度実行しても安全なので、毎回削除してから適用する。
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'delete', 'job', 'workboard-migrate', '--ignore-not-found'))
    $manifest = & kubectl kustomize $overlay
    if ($LASTEXITCODE -ne 0) { throw 'kubectl kustomize に失敗しました。' }
    ($manifest -join "`n").Replace($placeholderRegistry, $registry) | kubectl @common apply -f -
    if ($LASTEXITCODE -ne 0) { throw 'kubectl apply に失敗しました。' }
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', 'deployment/workboard-postgres', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'wait', '--for=condition=complete', 'job/workboard-migrate', '--timeout=300s'))
    foreach ($deployment in @('workboard-api', 'workboard-web')) {
        Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', "deployment/$deployment", '--timeout=180s'))
    }
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'get', 'pods,deploy,svc'))
    Write-Output '適用完了。README の port-forward 手順（8086 番）で画面を開いてください。'
}
finally { Pop-Location }
