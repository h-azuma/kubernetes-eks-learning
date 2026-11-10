#Requires -Version 5.1
# AWS Load Balancer Controller を Helm で導入・更新する。承認済みの AWS 環境でだけ手で実行する。
# 先に README の手順で helm template の生成物を読み、Terraform で IAM ロールと Pod Identity を作成済みであること。
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
$accountId = Confirm-AwsTarget
$context = "arn:aws:eks:${Region}:${accountId}:cluster/$ClusterName"
$vpcId = Get-TerraformOutput 'vpc_id'
Push-Location $RepositoryRoot
try {
    Invoke-Checked helm @('repo', 'add', 'eks', 'https://aws.github.io/eks-charts', '--force-update')
    Invoke-Checked helm @('repo', 'update', 'eks')
    # helm upgrade --install は初回だけ CRD を入れる。2 回目以降の upgrade は CRD を更新しない（README 参照）。
    Invoke-Checked helm @(
        'upgrade', '--install', 'aws-load-balancer-controller', 'eks/aws-load-balancer-controller',
        '--version', $LbcChartVersion,
        '--namespace', 'kube-system',
        '--kubeconfig', $LabKubeconfig, '--kube-context', $context,
        '--values', 'phases/07-aws-integration/helm/aws-load-balancer-controller-values.yaml',
        '--set', "clusterName=$ClusterName", '--set', "region=$Region", '--set', "vpcId=$vpcId")
    Invoke-Checked kubectl @('--kubeconfig', $LabKubeconfig, '--context', $context, '-n', 'kube-system', 'rollout', 'status', 'deployment/aws-load-balancer-controller', '--timeout=180s')
    Invoke-Checked helm @('list', '--namespace', 'kube-system', '--kubeconfig', $LabKubeconfig, '--kube-context', $context)
}
finally { Pop-Location }
