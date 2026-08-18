param([string]$Version = '')

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$RepoRoot = [IO.Path]::GetFullPath((Split-Path -Parent $ProjectRoot))
if (-not $Version) {
    $Version = (Get-Content -LiteralPath (Join-Path $ProjectRoot 'VERSION') -Raw).Trim()
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "版本号格式无效：$Version" }

$BuildRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '.release-build\devkit'))
$Workspace = Join-Path $BuildRoot 'workspace'
$DistRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'dist'))
$ReleaseRoot = [IO.Path]::GetFullPath((Join-Path $DistRoot "SeedVR2-Codex-DevKit-$Version-private"))

foreach ($Path in @($BuildRoot, $ReleaseRoot)) {
    if (-not $Path.StartsWith($ProjectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝清理项目外目录：$Path"
    }
}
if ((& git -C $RepoRoot status --porcelain --untracked-files=no)) {
    throw 'Git 工作区存在未提交修改；开发续接包必须从干净提交构建。'
}
if ($LASTEXITCODE -ne 0) { throw '无法检查 Git 工作区。' }
if (Test-Path -LiteralPath (Join-Path $RepoRoot '.git\worktrees')) {
    throw '当前仓库包含额外 Git worktree 元数据，不能生成可迁移快照。'
}

if (Test-Path -LiteralPath $BuildRoot) { Remove-Item -LiteralPath $BuildRoot -Recurse -Force }
if (Test-Path -LiteralPath $ReleaseRoot) { Remove-Item -LiteralPath $ReleaseRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Workspace, $ReleaseRoot | Out-Null

Write-Host '正在导出当前提交的源码与文档…'
$TrackedFiles = @(& git -c core.quotepath=false -C $RepoRoot ls-files)
if ($LASTEXITCODE -ne 0 -or $TrackedFiles.Count -eq 0) { throw '无法读取 Git 跟踪文件列表。' }
foreach ($Relative in $TrackedFiles) {
    $NativeRelative = $Relative -replace '/', '\'
    $Source = [IO.Path]::GetFullPath((Join-Path $RepoRoot $NativeRelative))
    $Target = [IO.Path]::GetFullPath((Join-Path $Workspace $NativeRelative))
    if (-not $Source.StartsWith($RepoRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
        -not $Target.StartsWith($Workspace + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Git 跟踪列表包含不安全路径：$Relative"
    }
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "Git 跟踪文件缺失：$Relative" }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Force
}

Write-Host '正在复制可迁移 Git 历史…'
$GitTarget = Join-Path $Workspace '.git'
New-Item -ItemType Directory -Force -Path $GitTarget | Out-Null
& (Join-Path $env:SystemRoot 'System32\robocopy.exe') (Join-Path $RepoRoot '.git') $GitTarget /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NP | Out-Host
if ($LASTEXITCODE -gt 7) { throw "Git 历史复制失败：$LASTEXITCODE" }

$WorkspaceArchive = Join-Path $ReleaseRoot 'workspace.zip'
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($Workspace, $WorkspaceArchive, [IO.Compression.CompressionLevel]::Optimal, $false)

foreach ($Name in @('Setup-SeedVR2-Dev.cmd', 'setup-dev.ps1', '开发续接说明.txt')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $Name) -Destination (Join-Path $ReleaseRoot $Name) -Force
}

$Head = (& git -C $RepoRoot rev-parse HEAD).Trim()
$Branch = (& git -C $RepoRoot branch --show-current).Trim()
$ArchiveHash = (Get-FileHash -LiteralPath $WorkspaceArchive -Algorithm SHA256).Hash
$Summary = [ordered]@{
    schemaVersion = 1
    version = $Version
    gitHead = $Head
    gitBranch = $Branch
    workspaceArchive = 'workspace.zip'
    workspaceBytes = (Get-Item -LiteralPath $WorkspaceArchive).Length
    workspaceSha256 = $ArchiveHash
    containsGitHistory = $true
    containsRuntime = $false
    containsModels = $false
    containsCredentials = $false
}
$Summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $ReleaseRoot 'devkit-summary.json') -Encoding UTF8

$SecretPatterns = ('sk-' + 'proj-|sk-' + 'ant-|OPENAI_' + 'API_KEY\s*=|ANTHROPIC_' + 'API_KEY\s*=|BEGIN (RSA |EC |OPENSSH )?PRIVATE ' + 'KEY')
$TextFiles = Get-ChildItem -LiteralPath $Workspace -Recurse -File | Where-Object { $_.Extension -in @('.py', '.ps1', '.cmd', '.bat', '.md', '.txt', '.json', '.yaml', '.yml') }
$SecretHits = @($TextFiles | Select-String -Pattern $SecretPatterns)
if ($SecretHits.Count -gt 0) { throw '开发续接包隐私扫描发现疑似凭证内容，已停止构建。' }

$HashLines = foreach ($File in (Get-ChildItem -LiteralPath $ReleaseRoot -Recurse -File | Sort-Object FullName)) {
    $Relative = $File.FullName.Substring($ReleaseRoot.Length + 1).Replace('\', '/')
    '{0}  {1}' -f (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash, $Relative
}
$HashLines | Set-Content -LiteralPath (Join-Path $ReleaseRoot 'SHA256SUMS.txt') -Encoding UTF8

Remove-Item -LiteralPath $BuildRoot -Recurse -Force
Write-Host "Codex 开发续接包已生成：$ReleaseRoot"
