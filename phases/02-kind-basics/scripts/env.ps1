#Requires -Version 5.1
. "$PSScriptRoot/../../../tools/kind-common.ps1"
$ClusterName = 'workboard-lab'
$ClusterContext = "kind-$ClusterName"
$LabKubeconfig = Join-Path $RepositoryRoot '.kube/workboard-kind.yaml'
Use-KindEnvironment $LabKubeconfig
