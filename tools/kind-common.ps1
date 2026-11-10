#Requires -Version 5.1
# Phase 2/3 の env.ps1・up.ps1 がドットソースで読み込む共通処理。
$RepositoryRoot = Split-Path $PSScriptRoot -Parent
$KindVersion = 'v0.33.0'
$ToolsDirectory = Join-Path $RepositoryRoot '.tools'

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command の実行に失敗しました（終了コード $LASTEXITCODE）。"
    }
}

function Use-KindEnvironment {
    param([string]$Kubeconfig)
    $env:KUBECONFIG = $Kubeconfig
    if (($env:PATH -split ';') -notcontains $ToolsDirectory) {
        $env:PATH = "$ToolsDirectory;$env:PATH"
    }
}

function Assert-KindPrerequisites {
    foreach ($tool in @('docker', 'kind', 'kubectl')) {
        if (-not (Get-Command $tool -CommandType Application -ErrorAction SilentlyContinue)) {
            throw "$tool がありません。先に Phase 2 の導入手順を実行してください。"
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
}

function Initialize-KindCluster {
    # Wait を空にすると --wait を付けない（CNI を後から入れる Phase 5 など、作成直後は Node が Ready にならない場合）。
    param([string]$Name, [string]$Kubeconfig, [string]$ConfigPath, [string]$Wait = '180s')
    $clusters = @(& kind get clusters)
    if ($LASTEXITCODE -ne 0) { throw 'kind クラスター一覧を取得できません。' }
    if ($clusters -notcontains $Name) {
        if (Test-Path $Kubeconfig) {
            throw 'クラスターはありませんが専用 kubeconfig が残っています。対象を確認してから対処してください。'
        }
        New-Item -ItemType Directory -Force (Split-Path $Kubeconfig) | Out-Null
        $arguments = @('create', 'cluster', '--name', $Name, '--config', $ConfigPath, '--kubeconfig', $Kubeconfig)
        if ($Wait) { $arguments += @('--wait', $Wait) }
        Invoke-Checked kind $arguments
    }
    elseif (-not (Test-Path $Kubeconfig)) {
        throw '同名クラスターが既にありますが、この教材の kubeconfig がありません。自動変更はしません。'
    }
}

function Import-WorkBoardImages {
    param([string]$ClusterName)
    Invoke-Checked docker @('build', '--provenance=false', '--target', 'runtime', '-t', 'workboard-api:kind', 'app/api')
    Invoke-Checked docker @('build', '--provenance=false', '-t', 'workboard-web:kind', 'app/web')
    Invoke-Checked kind @('load', 'docker-image', 'workboard-api:kind', 'workboard-web:kind', '--name', $ClusterName)
}
