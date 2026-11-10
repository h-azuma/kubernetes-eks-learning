#Requires -Version 5.1
. "$PSScriptRoot/../../../tools/kind-common.ps1"
$ClusterName = 'workboard-phase5'
$ClusterContext = "kind-$ClusterName"
$LabKubeconfig = Join-Path $RepositoryRoot '.kube/workboard-phase5.yaml'
Use-KindEnvironment $LabKubeconfig
