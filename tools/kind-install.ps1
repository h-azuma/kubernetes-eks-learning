#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/kind-common.ps1"
if (-not [Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
    throw 'このスクリプトは Windows x64 用です。他の OS/CPU は Phase 2 の手動手順を使ってください。'
}
New-Item -ItemType Directory -Force $ToolsDirectory | Out-Null
$kindPath = Join-Path $ToolsDirectory 'kind.exe'
if (Test-Path $kindPath) {
    $installed = & $kindPath version
    if ($LASTEXITCODE -ne 0 -or $installed -notmatch [regex]::Escape($KindVersion)) {
        throw '既存の .tools/kind.exe のバージョンが異なります。自動上書きはしません。'
    }
    Write-Output "kind $KindVersion は導入済みです。"
    return
}
$downloadPath = "$kindPath.download"
$url = "https://github.com/kubernetes-sigs/kind/releases/download/$KindVersion/kind-windows-amd64"
Write-Output "公式 kind $KindVersion を .tools に取得し、SHA-256 を検証します。"
Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $downloadPath
$checksum = (Invoke-WebRequest -UseBasicParsing -Uri "$url.sha256sum").Content
if ($checksum -is [byte[]]) { $checksum = [Text.Encoding]::UTF8.GetString($checksum) }
$expected = ($checksum.Trim() -split '\s+')[0]
if ($expected -notmatch '^[0-9a-fA-F]{64}$' -or (Get-FileHash $downloadPath -Algorithm SHA256).Hash -ne $expected) {
    throw 'kind の SHA-256 が一致しません。取得ファイルは実行しません。'
}
Move-Item -LiteralPath $downloadPath -Destination $kindPath
Invoke-Checked $kindPath @('version')
Write-Output 'この PowerShell で kind を使うには . ./phases/02-kind-basics/scripts/env.ps1 を実行してください。'
