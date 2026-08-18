param(
    [string]$Destination = '',
    [string]$InstalledRoot = ''
)

$ErrorActionPreference = 'Stop'
$PackageRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$Archive = Join-Path $PackageRoot 'workspace.zip'

if (-not $Destination) {
    $Destination = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'SeedVR2 Development'
}
if (-not $InstalledRoot) {
    $InstalledRoot = $env:SEEDVR2_INSTALL_ROOT
}
if (-not $InstalledRoot) {
    $InstalledRoot = Join-Path $env:LOCALAPPDATA 'Programs\SeedVR2 Upscaler'
}

$Destination = [IO.Path]::GetFullPath($Destination)
$InstalledRoot = [IO.Path]::GetFullPath($InstalledRoot)
$DestinationParent = [IO.Path]::GetFullPath((Split-Path -Parent $Destination))
$Staging = [IO.Path]::GetFullPath((Join-Path $DestinationParent ('.seedvr2-dev-setup-' + [guid]::NewGuid().ToString('N'))))
$ProjectRelative = 'seedvr2-upscaler'

if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) {
    throw '开发工作区归档缺失：workspace.zip'
}
foreach ($Required in @(
    'runtime\python\python.exe',
    'models\SEEDVR2\seedvr2_ema_7b_sharp-Q4_K_M.gguf',
    'models\SEEDVR2\ema_vae_fp16.safetensors'
)) {
    if (-not (Test-Path -LiteralPath (Join-Path $InstalledRoot $Required) -PathType Leaf)) {
        throw "基础安装不完整或路径错误：$InstalledRoot"
    }
}
if ((Get-Item -LiteralPath (Join-Path $InstalledRoot 'models\SEEDVR2\seedvr2_ema_7b_sharp-Q4_K_M.gguf')).Length -ne 4758306592) {
    throw '基础安装中的 SeedVR2 模型大小不符。'
}
if ((Get-Item -LiteralPath (Join-Path $InstalledRoot 'models\SEEDVR2\ema_vae_fp16.safetensors')).Length -ne 501324814) {
    throw '基础安装中的 VAE 模型大小不符。'
}
if (Test-Path -LiteralPath $Destination) {
    if (@(Get-ChildItem -LiteralPath $Destination -Force).Count -gt 0) {
        throw "目标目录不是空目录：$Destination"
    }
}
if (-not $Staging.StartsWith($DestinationParent + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw '无法创建安全的开发工作区临时目录。'
}

function Remove-Junction([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return }
    $Item = Get-Item -LiteralPath $Path -Force
    if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -eq 0) {
        throw "拒绝把普通目录当作联接删除：$Path"
    }
    [IO.Directory]::Delete($Path)
}

New-Item -ItemType Directory -Force -Path $DestinationParent | Out-Null
try {
    New-Item -ItemType Directory -Path $Staging | Out-Null
    Write-Host '正在解压 Codex 开发工作区…'
    Expand-Archive -LiteralPath $Archive -DestinationPath $Staging -Force

    $ProjectRoot = Join-Path $Staging $ProjectRelative
    $GitRoot = Join-Path $Staging '.git'
    $Handoff = Join-Path $Staging 'CODEX-HANDOFF.md'
    foreach ($Required in @($GitRoot, (Join-Path $ProjectRoot 'app\worker.py'), $Handoff)) {
        if (-not (Test-Path -LiteralPath $Required)) {
            throw "开发工作区缺少关键内容：$Required"
        }
    }

    $RuntimeLink = Join-Path $ProjectRoot 'runtime'
    $ModelsLink = Join-Path $ProjectRoot 'models'
    foreach ($Path in @($RuntimeLink, $ModelsLink)) {
        $Resolved = [IO.Path]::GetFullPath($Path)
        if (-not $Resolved.StartsWith([IO.Path]::GetFullPath($ProjectRoot) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw "拒绝替换项目外目录：$Resolved"
        }
        if (Test-Path -LiteralPath $Resolved) {
            Remove-Item -LiteralPath $Resolved -Recurse -Force
        }
    }

    New-Item -ItemType Junction -Path $RuntimeLink -Target (Join-Path $InstalledRoot 'runtime') | Out-Null
    New-Item -ItemType Junction -Path $ModelsLink -Target (Join-Path $InstalledRoot 'models') | Out-Null

    Write-Host '正在验证 Runtime、模型、CUDA 和 Git 工作区…'
    Push-Location $ProjectRoot
    try {
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'
        $env:PYTHONNOUSERSITE = '1'
        $env:PYTHONDONTWRITEBYTECODE = '1'
        & (Join-Path $RuntimeLink 'python\python.exe') -B -m app.cli check --cuda
        if ($LASTEXITCODE -ne 0) { throw "开发环境自检失败：$LASTEXITCODE" }
    } finally {
        Pop-Location
    }

    $Git = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($Git) {
        $Dirty = & $Git.Source -C $Staging status --porcelain
        if ($LASTEXITCODE -ne 0) { throw 'Git 工作区检查失败。' }
        if ($Dirty) { throw "开发工作区不是干净状态：$Dirty" }
    }

    if (Test-Path -LiteralPath $Destination) {
        Remove-Item -LiteralPath $Destination -Force
    }
    Move-Item -LiteralPath $Staging -Destination $Destination
    Write-Host ''
    Write-Host 'SeedVR2 Codex 开发工作区已就绪：'
    Write-Host $Destination
    Write-Host '请在 Codex 中打开此目录；AGENTS.md 会引导 Codex 先读取 CODEX-HANDOFF.md。'
} finally {
    if (Test-Path -LiteralPath $Staging) {
        $ProjectRoot = Join-Path $Staging $ProjectRelative
        foreach ($Link in @((Join-Path $ProjectRoot 'runtime'), (Join-Path $ProjectRoot 'models'))) {
            if (Test-Path -LiteralPath $Link) {
                $Item = Get-Item -LiteralPath $Link -Force
                if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                    Remove-Junction $Link
                }
            }
        }
        Remove-Item -LiteralPath $Staging -Recurse -Force
    }
}
