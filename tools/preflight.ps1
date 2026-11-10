#Requires -Version 5.1
$ErrorActionPreference = 'Continue'
$gitAvailable = $false

function Show-ToolVersion {
    param(
        [string]$Name,
        [string]$Command,
        [string[]]$VersionArguments
    )

    if (-not (Get-Command $Command -CommandType Application -ErrorAction SilentlyContinue)) {
        Write-Output "[未導入] $Name : コマンドが見つかりません"
        return $false
    }

    try {
        $output = & $Command @VersionArguments 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Output "[確認失敗] $Name : バージョン取得の終了コード $LASTEXITCODE"
            return $false
        }
        $version = ($output | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ }) -join ' / '
        if (-not $version) {
            Write-Output "[確認失敗] $Name : バージョン出力がありません"
            return $false
        }
        Write-Output "[利用可能] $Name : $version"
        return $true
    }
    catch {
        Write-Output "[確認失敗] $Name : バージョンを取得できません"
        return $false
    }
}

Write-Output '環境確認（バージョン表示のみ。稼働状態・互換性は未確認）'
$checks = @(
    @{ Name = 'Git'; Command = 'git'; Arguments = @('--version') },
    @{ Name = 'Docker'; Command = 'docker'; Arguments = @('--version') },
    @{ Name = 'Docker Compose'; Command = 'docker'; Arguments = @('compose', 'version') },
    @{ Name = 'kubectl'; Command = 'kubectl'; Arguments = @('version', '--client=true', '--output=yaml') },
    @{ Name = 'kind'; Command = 'kind'; Arguments = @('version') },
    @{ Name = 'Python'; Command = 'python'; Arguments = @('--version') },
    @{ Name = 'Node.js'; Command = 'node'; Arguments = @('--version') },
    @{ Name = 'AWS CLI'; Command = 'aws'; Arguments = @('--version') },
    @{ Name = 'Terraform'; Command = 'terraform'; Arguments = @('version') }
)

foreach ($check in $checks) {
    $result = @(Show-ToolVersion -Name $check.Name -Command $check.Command -VersionArguments $check.Arguments)
    $available = $result[-1]
    $result | Select-Object -SkipLast 1 | Write-Output
    if ($check.Name -eq 'Git') { $gitAvailable = $available }
}

if (-not $gitAvailable) {
    Write-Output 'Phase 0 必須の Git を確認してください。'
    exit 1
}
Write-Output 'Phase 0 の必須ツールを確認しました。他ツールの不足は後続フェーズで対応できます。'
exit 0
