#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path $PSScriptRoot -Parent
$portalRoot = Join-Path $repositoryRoot 'learning-portal'
$listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, 8765)
try {
    $listener.Start()
}
catch {
    throw '127.0.0.1:8765 は使用中です。既存プロセスは停止しません。起動済みならブラウザーで同じURLを開いてください。'
}
finally {
    $listener.Stop()
}
foreach ($name in @('python', 'npm.cmd')) {
    if (-not (Get-Command $name -CommandType Application -ErrorAction SilentlyContinue)) {
        throw "$name がありません。Python と Node.js の導入状況を確認してください。"
    }
}
Push-Location $repositoryRoot
try {
    Write-Output '教材を更新し、学習画面をビルドします。WorkBoard や kind は操作しません。'
    & python (Join-Path $portalRoot 'content/build_content.py')
    if ($LASTEXITCODE -ne 0) { throw '教材データの生成に失敗しました。' }
    $lockPath = Join-Path $portalRoot 'package-lock.json'
    $installedLock = Join-Path $portalRoot 'node_modules/.package-lock.json'
    if (-not (Test-Path $lockPath)) { throw 'package-lock.json がありません。リポジトリの内容を確認してください。' }
    if (-not (Test-Path $installedLock) -or (Get-Item $lockPath).LastWriteTimeUtc -gt (Get-Item $installedLock).LastWriteTimeUtc) {
        & npm.cmd --prefix $portalRoot ci
        if ($LASTEXITCODE -ne 0) { throw '学習画面の依存パッケージを導入できませんでした。' }
    }
    & npm.cmd --prefix $portalRoot run build
    if ($LASTEXITCODE -ne 0) { throw '学習画面のビルドに失敗しました。' }
    & python (Join-Path $portalRoot 'server.py')
    if ($LASTEXITCODE -ne 0) { throw '学習ポータルを起動できませんでした。' }
}
finally {
    Pop-Location
}
