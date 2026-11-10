#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
$CalicoManifest = 'https://raw.githubusercontent.com/projectcalico/calico/v3.33.0/manifests/calico.yaml'
Push-Location $RepositoryRoot
try {
    Assert-KindPrerequisites
    # 既定の CNI を無効にした kind は、CNI を入れるまで Node が Ready にならないため、--wait なしで作成する。
    Initialize-KindCluster $ClusterName $LabKubeconfig 'phases/05-security-and-failure/cluster.yaml' ''
    $common = @('--kubeconfig', $LabKubeconfig, '--context', $ClusterContext)
    # 存在しない名前の get は stderr に出力して停止するため、ラベル検索の出力が空かどうかで判定する。
    if (-not (& kubectl @common -n kube-system get daemonset -l k8s-app=calico-node -o name)) {
        # CRD が大きく apply だと上限を超えることがあるため、公式手順どおり create を使う。
        Invoke-Checked kubectl ($common + @('create', '-f', $CalicoManifest))
    }
    Invoke-Checked kubectl ($common + @('-n', 'kube-system', 'rollout', 'status', 'daemonset/calico-node', '--timeout=300s'))
    Invoke-Checked kubectl ($common + @('-n', 'kube-system', 'rollout', 'status', 'deployment/calico-kube-controllers', '--timeout=300s'))
    Invoke-Checked kubectl ($common + @('wait', '--for=condition=Ready', 'node', '--all', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('-n', 'kube-system', 'rollout', 'status', 'deployment/coredns', '--timeout=180s'))
    Import-WorkBoardImages $ClusterName
    $secretFile = Join-Path $RepositoryRoot 'phases/05-security-and-failure/kustomize/overlays/kind/secrets/db.env'
    if (-not (Test-Path $secretFile)) {
        $bytes = New-Object byte[] 24
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $password = -join ($bytes | ForEach-Object { $_.ToString('x2') })
        [IO.File]::WriteAllText($secretFile, "POSTGRES_PASSWORD=$password`n", (New-Object Text.UTF8Encoding $false))
        Write-Output "ローカル専用の DB パスワードを生成しました（値は表示しません）: $secretFile"
    }
    # 完了済み Job の spec は変更できない。Alembic は何度実行しても安全なので、毎回削除してから適用する。
    # 初回は Namespace が無いが、--ignore-not-found により Job の削除はエラーにならない。
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'delete', 'job', 'workboard-migrate', '--ignore-not-found'))
    Invoke-Checked kubectl ($common + @('apply', '-k', 'phases/05-security-and-failure/kustomize/overlays/kind'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', 'statefulset/workboard-postgres', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'wait', '--for=condition=complete', 'job/workboard-migrate', '--timeout=300s'))
    foreach ($deployment in @('workboard-api', 'workboard-web')) {
        Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', "deployment/$deployment", '--timeout=180s'))
    }
    Invoke-Checked kubectl ($common + @('get', 'nodes'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'get', 'pods,sts,deploy,svc,sa,networkpolicy'))
    Write-Output '構築完了。Phase 5 の port-forward 手順（8083 番）で画面を開いてください。'
}
finally { Pop-Location }
