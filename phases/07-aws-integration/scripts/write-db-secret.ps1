#Requires -Version 5.1
# RDS のマスターパスワードを Secrets Manager から取り出し、Git 管理外の Secret 入力ファイル db.env を作る。
# 値は表示しない。承認済みの AWS 環境でだけ手で実行する。
# RDS 管理のパスワードは既定で 7 日ごとに自動で変わる。変わったらこのスクリプトを再実行して deploy し直す。
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"
Confirm-AwsTarget | Out-Null
$secretFile = Join-Path $RepositoryRoot 'phases/07-aws-integration/kustomize/overlays/eks/secrets/db.env'
$secretArn = Get-TerraformOutput 'db_master_secret_arn'

$secretJson = & aws secretsmanager get-secret-value --secret-id $secretArn --region $Region --query SecretString --output text
if ($LASTEXITCODE -ne 0) { throw 'Secrets Manager からパスワードを取得できません。' }
$password = ($secretJson | ConvertFrom-Json).password
[IO.File]::WriteAllText($secretFile, "POSTGRES_PASSWORD=$password`n", (New-Object Text.UTF8Encoding $false))
Write-Output "DB パスワードを書き出しました（値は表示しません）: $secretFile"
