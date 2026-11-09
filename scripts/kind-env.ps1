#Requires -Version 5.1
$RepositoryRoot = Split-Path $PSScriptRoot -Parent
$KindVersion = 'v0.33.0'
$ClusterName = 'workboard-lab'
$ClusterContext = "kind-$ClusterName"
$ToolsDirectory = Join-Path $RepositoryRoot '.tools'
$LabKubeconfig = Join-Path $RepositoryRoot '.kube/workboard-kind.yaml'
$env:KUBECONFIG = $LabKubeconfig
if (($env:PATH -split ';') -notcontains $ToolsDirectory) {
    $env:PATH = "$ToolsDirectory;$env:PATH"
}

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command の実行に失敗しました（終了コード $LASTEXITCODE）。"
    }
}
