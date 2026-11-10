#Requires -Version 5.1
# WorkBoard の API/Web イメージをビルドして ECR へ push する。ECR リポジトリは Terraform で作成済みであること。
# 承認済みの AWS 環境でだけ手で実行する。タグは kustomize/overlays/eks の newTag と同じ phase6。
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
$accountId = Confirm-AwsTarget
$registry = "$accountId.dkr.ecr.$Region.amazonaws.com"
Push-Location $RepositoryRoot
try {
    $password = & aws ecr get-login-password --region $Region
    if ($LASTEXITCODE -ne 0) { throw 'ECR のログイン用パスワードを取得できません。' }
    $password | docker login --username AWS --password-stdin $registry
    if ($LASTEXITCODE -ne 0) { throw 'ECR へのログインに失敗しました。' }

    # EKS のノードは x86_64。Apple Silicon などでも linux/amd64 を明示してビルドする。
    Invoke-Checked docker @('build', '--platform', 'linux/amd64', '--provenance=false', '--target', 'runtime', '-t', "$registry/workboard-api:phase6", 'app/api')
    Invoke-Checked docker @('build', '--platform', 'linux/amd64', '--provenance=false', '-t', "$registry/workboard-web:phase6", 'app/web')
    Invoke-Checked docker @('push', "$registry/workboard-api:phase6")
    Invoke-Checked docker @('push', "$registry/workboard-web:phase6")
    Write-Output 'push 完了。'
}
finally { Pop-Location }
