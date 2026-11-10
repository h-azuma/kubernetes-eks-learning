#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
Push-Location $RepositoryRoot
try {
    Assert-KindPrerequisites
    Initialize-KindCluster $ClusterName $LabKubeconfig 'phases/02-kind-basics/cluster.yaml'
    Import-WorkBoardImages $ClusterName
    $common = @('--kubeconfig', $LabKubeconfig, '--context', $ClusterContext)
    Invoke-Checked kubectl ($common + @('apply', '-f', 'phases/02-kind-basics/manifests/namespace.yaml'))
    Invoke-Checked kubectl ($common + @('apply', '-f', 'phases/02-kind-basics/manifests/postgres.yaml'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', 'deployment/workboard-postgres', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('apply', '-f', 'phases/02-kind-basics/manifests/migrate.yaml'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'wait', '--for=condition=complete', 'job/workboard-migrate', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('apply', '-f', 'phases/02-kind-basics/manifests/app.yaml'))
    foreach ($deployment in @('workboard-api', 'workboard-web')) {
        Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', "deployment/$deployment", '--timeout=180s'))
    }
    Invoke-Checked kubectl ($common + @('get', 'nodes'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'get', 'pods,rs,deploy,svc'))
    Write-Output '構築完了。Phase 2 の port-forward 手順で画面を開いてください。'
}
finally { Pop-Location }
