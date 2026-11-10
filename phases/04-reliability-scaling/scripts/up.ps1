#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
Push-Location $RepositoryRoot
try {
    Assert-KindPrerequisites
    Initialize-KindCluster $ClusterName $LabKubeconfig 'phases/04-reliability-scaling/cluster.yaml'
    Import-WorkBoardImages $ClusterName
    $common = @('--kubeconfig', $LabKubeconfig, '--context', $ClusterContext)
    $secretFile = Join-Path $RepositoryRoot 'phases/04-reliability-scaling/kustomize/overlays/kind/secrets/db.env'
    if (-not (Test-Path $secretFile)) {
        $bytes = New-Object byte[] 24
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $password = -join ($bytes | ForEach-Object { $_.ToString('x2') })
        [IO.File]::WriteAllText($secretFile, "POSTGRES_PASSWORD=$password`n", (New-Object Text.UTF8Encoding $false))
        Write-Output "ローカル専用の DB パスワードを生成しました（値は表示しません）: $secretFile"
    }
    # metrics-server は kube-system に入れる。HPA が CPU を読むために必要。
    Invoke-Checked kubectl ($common + @('apply', '-k', 'phases/04-reliability-scaling/kustomize/metrics-server'))
    # 完了済み Job の spec は変更できない。Alembic は何度実行しても安全なので、毎回削除してから適用する。
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'delete', 'job', 'workboard-migrate', '--ignore-not-found'))
    Invoke-Checked kubectl ($common + @('apply', '-k', 'phases/04-reliability-scaling/kustomize/overlays/kind'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', 'statefulset/workboard-postgres', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'wait', '--for=condition=complete', 'job/workboard-migrate', '--timeout=300s'))
    foreach ($deployment in @('workboard-api', 'workboard-web')) {
        Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', "deployment/$deployment", '--timeout=180s'))
    }
    Invoke-Checked kubectl ($common + @('-n', 'kube-system', 'rollout', 'status', 'deployment/metrics-server', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('wait', '--for=condition=Available', 'apiservice/v1beta1.metrics.k8s.io', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('get', 'nodes'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'get', 'pods,sts,deploy,svc,pvc,hpa,pdb', '-o', 'wide'))
    Write-Output '構築完了。Phase 4 の port-forward 手順（8082 番）で画面を開いてください。'
}
finally { Pop-Location }
