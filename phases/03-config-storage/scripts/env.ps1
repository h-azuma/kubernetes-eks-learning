#Requires -Version 5.1
. "$PSScriptRoot/../../../tools/kind-common.ps1"
$ClusterName = 'workboard-phase3'
$ClusterContext = "kind-$ClusterName"
$LabKubeconfig = Join-Path $RepositoryRoot '.kube/workboard-phase3.yaml'
Use-KindEnvironment $LabKubeconfig
