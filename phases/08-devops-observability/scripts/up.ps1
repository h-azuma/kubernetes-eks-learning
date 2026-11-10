#Requires -Version 5.1
# Phase 8 の kind クラスターを構築・更新する（up.sh と同じ内容）。
# Argo CD が同期するリポジトリ: 環境変数 GITOPS_REPO_URL があればその URL、なければこの clone の origin。
# リビジョン: 環境変数 GITOPS_REVISION があればその値、なければ今のブランチ。
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/env.ps1"

function Get-GitValue {
    param([string[]]$Arguments)
    # git の失敗は戻り値で判断する（理由は git のメッセージとして表示される）。
    $ErrorActionPreference = 'Continue'
    $value = & git -C $RepositoryRoot @Arguments
    if ($LASTEXITCODE -eq 0) { "$value".Trim() }
}

function Get-GitOpsRepoUrl {
    $url = $env:GITOPS_REPO_URL
    if (-not $url) { $url = Get-GitValue @('remote', 'get-url', 'origin') }
    if (-not $url) {
        throw 'Argo CD が同期するリポジトリの URL が分かりません。環境変数 GITOPS_REPO_URL に、自分が push できる公開リポジトリの HTTPS の URL を設定してください。'
    }
    # SSH 形式は鍵が要るため公開リポジトリの HTTPS に直し、URL に含まれる認証情報は取り除く。
    $url -replace '^(ssh://)?git@([^:/]+)[:/]', 'https://$2/' -replace '^https://[^@/]+@', 'https://'
}

function Get-GitOpsRevision {
    $revision = $env:GITOPS_REVISION
    if (-not $revision) { $revision = Get-GitValue @('rev-parse', '--abbrev-ref', 'HEAD') }
    if (-not $revision -or $revision -eq 'HEAD') {
        throw '同期するブランチが分かりません。環境変数 GITOPS_REVISION にブランチまたはタグを設定してください。'
    }
    $revision
}
Push-Location $RepositoryRoot
try {
    Assert-KindPrerequisites
    Initialize-KindCluster $ClusterName $LabKubeconfig 'phases/08-devops-observability/cluster.yaml'
    Import-WorkBoardImages $ClusterName
    $common = @('--kubeconfig', $LabKubeconfig, '--context', $ClusterContext)
    $phase = 'phases/08-devops-observability'
    $secretFile = Join-Path $RepositoryRoot "$phase/kustomize/overlays/kind/secrets/db.env"
    if (-not (Test-Path $secretFile)) {
        $bytes = New-Object byte[] 24
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        $password = -join ($bytes | ForEach-Object { $_.ToString('x2') })
        [IO.File]::WriteAllText($secretFile, "POSTGRES_PASSWORD=$password`n", (New-Object Text.UTF8Encoding $false))
        Write-Output "ローカル専用の DB パスワードを生成しました（値は表示しません）: $secretFile"
    }
    # kubectl create --dry-run の出力を apply して、既にあるリソースでも失敗しないようにする。
    function Invoke-ApplyGenerated([string[]]$CreateArguments) {
        $yaml = & kubectl @($common + $CreateArguments + @('--dry-run=client', '-o', 'yaml'))
        if ($LASTEXITCODE -ne 0) { throw 'kubectl create の生成に失敗しました。' }
        $yaml | & kubectl @($common + @('apply', '-f', '-'))
        if ($LASTEXITCODE -ne 0) { throw 'kubectl apply に失敗しました。' }
    }
    # Secret は Git に入れられないため、Argo CD の同期対象には含めず、ここで作る（decisions/0015）。
    Invoke-ApplyGenerated @('create', 'namespace', 'workboard')
    Invoke-ApplyGenerated @('-n', 'workboard', 'create', 'secret', 'generic', 'workboard-db', "--from-env-file=$secretFile")
    # 完了済み Job の spec は変更できない。Alembic は何度実行しても安全なので、毎回削除してから適用する。
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'delete', 'job', 'workboard-migrate', '--ignore-not-found'))
    Invoke-Checked kubectl ($common + @('apply', '-k', "$phase/kustomize/overlays/kind"))

    Invoke-ApplyGenerated @('create', 'namespace', 'argocd')
    # CRD が大きく client-side apply の annotation 上限を超えるため、server-side apply を使う。
    Invoke-Checked kubectl ($common + @('apply', '-n', 'argocd', '--server-side', '--force-conflicts', '-f', $ArgoCdInstallUrl))
    Invoke-Checked kubectl ($common + @('apply', '-k', "$phase/kustomize/monitoring"))

    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', 'statefulset/workboard-postgres', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'wait', '--for=condition=complete', 'job/workboard-migrate', '--timeout=300s'))
    foreach ($deployment in @('workboard-api', 'workboard-web')) {
        Invoke-Checked kubectl ($common + @('-n', 'workboard', 'rollout', 'status', "deployment/$deployment", '--timeout=180s'))
    }
    Invoke-Checked kubectl ($common + @('-n', 'monitoring', 'rollout', 'status', 'deployment/prometheus', '--timeout=180s'))
    Invoke-Checked kubectl ($common + @('-n', 'argocd', 'rollout', 'status', 'statefulset/argocd-application-controller', '--timeout=300s'))
    Invoke-Checked kubectl ($common + @('-n', 'argocd', 'wait', '--for=condition=Available', 'deployment', '--all', '--timeout=300s'))
    Invoke-Checked kubectl ($common + @('wait', '--for=condition=Established', 'crd/applications.argoproj.io', '--timeout=60s'))

    $source = @{ repoURL = Get-GitOpsRepoUrl; targetRevision = Get-GitOpsRevision }
    Write-Output "Argo CD の同期対象: $($source.repoURL)（$($source.targetRevision)）"
    Invoke-Checked kubectl ($common + @('apply', '-f', "$phase/argocd/application.yaml"))
    $patch = @{ spec = @{ source = $source } } | ConvertTo-Json -Depth 5 -Compress
    # Windows PowerShell 5.1 は引数内の " を渡すとき \" にする必要がある。
    Invoke-Checked kubectl ($common + @('-n', 'argocd', 'patch', 'application', 'workboard', '--type', 'merge', '-p', $patch.Replace('"', '\"')))
    Invoke-Checked kubectl ($common + @('get', 'nodes'))
    Invoke-Checked kubectl ($common + @('-n', 'workboard', 'get', 'pods,sts,deploy,svc,pvc,pdb', '-o', 'wide'))
    Invoke-Checked kubectl ($common + @('-n', 'monitoring', 'get', 'pods'))
    Invoke-Checked kubectl ($common + @('-n', 'argocd', 'get', 'pods,application'))
    Write-Output '構築完了。Phase 8 の port-forward 手順（WorkBoard 8084、Argo CD 8085、Prometheus 8087）で画面を開いてください。'
    Write-Output 'Application は Git に push 済みのリビジョンだけを同期できます。README の「検証コマンド・期待結果」の 5・6 の手順を確認してください。'
}
finally { Pop-Location }
