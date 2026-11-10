#Requires -Version 5.1
# EKS クラスターに接続するための専用 kubeconfig（.kube/workboard-eks.yaml）を作成・更新する。
# 承認済みの AWS 環境でだけ手で実行する。
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
Confirm-AwsTarget | Out-Null
Invoke-Checked aws @('eks', 'update-kubeconfig', '--name', $ClusterName, '--region', $Region, '--kubeconfig', $LabKubeconfig)
Invoke-Checked kubectl @('--kubeconfig', $LabKubeconfig, 'get', 'nodes')
