#Requires -Version 5.1
# ドットソースして使う: . .\phases\07-aws-integration\scripts\env.ps1
# このシェルだけで、EKS 用の kubeconfig（.kube/workboard-eks.yaml）と AWS のリージョンを設定する。
# AWS の操作はしない。AWS を操作する各スクリプトは Confirm-AwsTarget で対象を確認してから進む。
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$Region = if ($env:AWS_REGION) { $env:AWS_REGION } else { 'ap-northeast-1' }
$ClusterName = if ($env:EKS_CLUSTER_NAME) { $env:EKS_CLUSTER_NAME } else { 'workboard-learning' }
$LabKubeconfig = Join-Path $RepositoryRoot '.kube/workboard-eks.yaml'
$env:AWS_REGION = $Region
$env:KUBECONFIG = $LabKubeconfig

function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command の実行に失敗しました（終了コード $LASTEXITCODE）。"
    }
}

# 操作対象のアカウント・リージョン・クラスターを表示し、yes と入力した場合だけ続行する。アカウント ID を返す。
function Confirm-AwsTarget {
    $json = & aws sts get-caller-identity --output json
    if ($LASTEXITCODE -ne 0) { throw 'aws sts get-caller-identity に失敗しました。認証情報を確認してください。' }
    $identity = $json | ConvertFrom-Json
    Write-Host "AWS アカウント: $($identity.Account)"
    Write-Host "呼び出し元     : $($identity.Arn)"
    Write-Host "リージョン     : $Region"
    Write-Host "クラスター名   : $ClusterName"
    $answer = Read-Host 'この対象で AWS を操作します。続行するには yes と入力してください'
    if ($answer -ne 'yes') { throw '中止しました。' }
    return $identity.Account
}

# Phase 7 で固定する AWS Load Balancer Controller の chart バージョン（helm/aws-load-balancer-controller-values.yaml と同じ版）。
$LbcChartVersion = '3.6.2'
$TerraformDirectory = Join-Path $RepositoryRoot 'phases/07-aws-integration/terraform'

# terraform output の値を 1 つ返す（terraform apply 済みで、state がこのディレクトリにあること）。
function Get-TerraformOutput {
    param([string]$Name)
    $value = & terraform "-chdir=$TerraformDirectory" output -raw $Name
    if ($LASTEXITCODE -ne 0) { throw "terraform output $Name を取得できません。apply 済みか確認してください。" }
    return $value
}
