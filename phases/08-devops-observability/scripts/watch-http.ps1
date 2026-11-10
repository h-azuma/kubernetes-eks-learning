#Requires -Version 5.1
# HTTP 応答を一定間隔で記録する（watch-http.sh の PowerShell 版）。復旧時間の測定に使う。
# 使い方: powershell -NoProfile -File watch-http.ps1 [URL] [間隔の秒数] [回数（0 は Ctrl+C まで）]
# 出力: 時刻 HTTP ステータス 所要秒数（接続できないときのステータスは 000）
param(
    [string]$Url = 'http://localhost:8084/api/v1/tasks',
    [double]$Interval = 1,
    [int]$Count = 0
)
$i = 0
while ($Count -eq 0 -or $i -lt $Count) {
    $result = & curl.exe -s -o NUL --max-time 2 -w '%{http_code} %{time_total}' $Url
    if (-not $result) { $result = '000 0' }
    Write-Output ('{0} {1}' -f (Get-Date -Format 'HH:mm:ss'), $result)
    $i++
    Start-Sleep -Seconds $Interval
}
