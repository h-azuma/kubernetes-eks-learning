#Requires -Version 5.1
. "$PSScriptRoot/../../../tools/kind-common.ps1"
$ClusterName = 'workboard-phase8'
$ClusterContext = "kind-$ClusterName"
$LabKubeconfig = Join-Path $RepositoryRoot '.kube/workboard-phase8.yaml'
# Argo CD は v3.6.1 の公式 install.yaml を、コミット SHA で固定した URL から取得する（decisions/0015）。
$ArgoCdInstallUrl = 'https://raw.githubusercontent.com/argoproj/argo-cd/94037c4d4e1af4bd0651d37a179fbd9e347e668c/manifests/install.yaml'
Use-KindEnvironment $LabKubeconfig
