#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/kind-env.ps1"
Push-Location $RepositoryRoot
try {
    foreach ($tool in @('docker', 'kind', 'kubectl')) {
        if (-not (Get-Command $tool -CommandType Application -ErrorAction SilentlyContinue)) {
            throw "$tool がありません。先に Lab 02 の導入手順を実行してください。"
        }
    }
    $client = (& kubectl version --client=true --output=json | ConvertFrom-Json).clientVersion
    if ($LASTEXITCODE -ne 0 -or $client.major -ne '1' -or [int]($client.minor -replace '\D', '') -notin 34..36) {
        throw 'この Kubernetes 1.35 ラボには kubectl 1.34〜1.36 が必要です。'
    }
    $dockerOS = & docker info --format '{{.OSType}}'
    if ($LASTEXITCODE -ne 0 -or $dockerOS -ne 'linux') {
        throw 'Docker Desktop の Linux コンテナエンジンを起動してください。'
    }
    $clusters = @(& kind get clusters)
    if ($LASTEXITCODE -ne 0) { throw 'kind クラスター一覧を取得できません。' }
    if ($clusters -notcontains $ClusterName) {
        if (Test-Path $LabKubeconfig) {
            throw 'クラスターはありませんが専用 kubeconfig が残っています。対象を確認してから対処してください。'
        }
        New-Item -ItemType Directory -Force (Split-Path $LabKubeconfig) | Out-Null
        Invoke-Checked kind @('create', 'cluster', '--name', $ClusterName, '--config', 'kubernetes/kind/cluster.yaml', '--kubeconfig', $LabKubeconfig, '--wait', '180s')
    }
    elseif (-not (Test-Path $LabKubeconfig)) {
        throw '同名クラスターが既にありますが、この教材の kubeconfig がありません。自動変更はしません。'
    }
    Invoke-Checked docker @('build', '--provenance=false', '--target', 'runtime', '-t', 'workboard-api:kind', 'app/api')
    Invoke-Checked docker @('build', '--provenance=false', '-t', 'workboard-web:kind', 'app/web')
    Invoke-Checked kind @('load', 'docker-image', 'workboard-api:kind', 'workboard-web:kind', '--name', $ClusterName)
    $common = @('--kubeconfig', $LabKubeconfig, '--context', $ClusterContext)
    Invoke-Checked kubectl ($common + @('apply', '-f', 'kubernetes/kind/namespace.yaml'))
    Invoke-Checked kubectl ($common + @('apply', '-f', 'kubernetes/kind/postgres.yaml'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', 'deployment/workboard-postgres', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('apply', '-f', 'kubernetes/kind/migrate.yaml'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'wait', '--for=condition=complete', 'job/workboard-migrate', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('apply', '-f', 'kubernetes/kind/app.yaml'))
    foreach ($deployment in @('workboard-api', 'workboard-web')) {
        Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', "deployment/$deployment", '--timeout=180s'))
    }
    Invoke-Checked kubectl ($common + @('get', 'nodes'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'get', 'pods,rs,deploy,svc'))
    Write-Output '構築完了。Lab 02 の port-forward 手順で画面を開いてください。'
}
finally { Pop-Location }
