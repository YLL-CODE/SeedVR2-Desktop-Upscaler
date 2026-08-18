param([string]$Destination = '')

$ErrorActionPreference = 'Stop'
$PackageRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$PayloadRoot = [IO.Path]::GetFullPath((Join-Path $PackageRoot 'payload'))
$ManifestPath = Join-Path $PackageRoot 'update-manifest.json'
$IsTest = $env:SEEDVR2_RELEASE_TEST -eq '1'

if (-not $Destination) { $Destination = $env:SEEDVR2_INSTALL_ROOT }
if (-not $Destination) {
    $RegisteredInstall = Get-ItemPropertyValue -LiteralPath 'HKCU:\Software\SeedVR2Upscaler' -Name InstallLocation -ErrorAction SilentlyContinue
    if ($RegisteredInstall) { $Destination = $RegisteredInstall }
}
if (-not $Destination) {
    $RegisteredInstall = Get-ItemPropertyValue -LiteralPath 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SeedVR2Upscaler' -Name InstallLocation -ErrorAction SilentlyContinue
    if ($RegisteredInstall) { $Destination = $RegisteredInstall }
}
if (-not $Destination) { $Destination = Join-Path $env:LOCALAPPDATA 'Programs\SeedVR2 Upscaler' }
$Destination = [IO.Path]::GetFullPath($Destination)

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw '更新清单缺失。' }
if (-not (Test-Path -LiteralPath $PayloadRoot -PathType Container)) { throw '更新 payload 缺失。' }
foreach ($Required in @('VERSION', 'app\worker.py', 'runtime\python\python.exe', 'requirements-lock.txt')) {
    if (-not (Test-Path -LiteralPath (Join-Path $Destination $Required))) {
        throw "没有找到有效的 SeedVR2 基础安装：$Destination"
    }
}

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$InstalledVersion = (Get-Content -LiteralPath (Join-Path $Destination 'VERSION') -Raw).Trim()
if ($InstalledVersion -notin @($Manifest.compatibleInstalledVersions)) {
    throw "当前安装版本 $InstalledVersion 不在本更新支持范围内：$($Manifest.compatibleInstalledVersions -join ', ')"
}

function Get-Sha256([string]$Path) {
    $Stream = [IO.File]::OpenRead($Path)
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($Hasher.ComputeHash($Stream)).Replace('-', '')
    } finally {
        $Hasher.Dispose()
        $Stream.Dispose()
    }
}

function Get-RequirementsHash([string]$Path) {
    $Lines = @(
        Get-Content -LiteralPath $Path -Encoding UTF8 |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and -not $_.StartsWith('#') }
    )
    $Bytes = [Text.UTF8Encoding]::new($false).GetBytes(($Lines -join "`n"))
    $Hasher = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($Hasher.ComputeHash($Bytes)).Replace('-', '')
    } finally {
        $Hasher.Dispose()
    }
}

$InstalledLockHash = Get-RequirementsHash (Join-Path $Destination 'requirements-lock.txt')
if ($InstalledLockHash -ne $Manifest.runtimeLockSha256) {
    throw '基础安装的 Python 依赖与本代码更新不兼容，请改用完整安装包。'
}
foreach ($Model in @($Manifest.models)) {
    $Path = Join-Path $Destination ($Model.path -replace '/', '\')
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf) -or (Get-Item -LiteralPath $Path).Length -ne $Model.bytes) {
        throw "基础安装模型不兼容：$($Model.path)"
    }
}

Write-Host '正在校验代码更新包…'
foreach ($Entry in @($Manifest.files)) {
    $Relative = $Entry.path -replace '/', '\'
    $Source = [IO.Path]::GetFullPath((Join-Path $PayloadRoot $Relative))
    if (-not $Source.StartsWith($PayloadRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "更新清单包含不安全路径：$($Entry.path)"
    }
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "更新文件缺失：$($Entry.path)" }
    if ((Get-Item -LiteralPath $Source).Length -ne $Entry.bytes) { throw "更新文件大小不符：$($Entry.path)" }
    if ((Get-Sha256 $Source) -ne $Entry.sha256) { throw "更新文件校验失败：$($Entry.path)" }
}

$Running = @(
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.ExecutablePath -and
            [IO.Path]::GetFullPath($_.ExecutablePath).StartsWith($Destination + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
        }
)
if ($Running.Count -gt 0) {
    throw 'SeedVR2 当前仍在运行。请关闭工具后重新安装更新。'
}

$ManagedDirectories = @($Manifest.managedDirectories)
$ManagedFiles = @($Manifest.managedFiles)
$AllowedDirectories = @('app', 'assets', 'vendor')
$AllowedFiles = @('README.md', 'VERSION', '启动 SeedVR2 放大工具.bat')
if (@($ManagedDirectories | Where-Object { $_ -notin $AllowedDirectories }).Count -gt 0 -or @($AllowedDirectories | Where-Object { $_ -notin $ManagedDirectories }).Count -gt 0 -or $ManagedDirectories.Count -ne $AllowedDirectories.Count) {
    throw '更新清单请求替换非代码目录。'
}
if (@($ManagedFiles | Where-Object { $_ -notin $AllowedFiles }).Count -gt 0 -or @($AllowedFiles | Where-Object { $_ -notin $ManagedFiles }).Count -gt 0 -or $ManagedFiles.Count -ne $AllowedFiles.Count) {
    throw '更新清单请求替换非应用文件。'
}
foreach ($Name in @($ManagedDirectories + $ManagedFiles)) {
    if ($Name -notmatch '^[^\\/:*?""<>|]+$') { throw "更新清单包含无效管理项：$Name" }
    if ($Name -ne 'assets' -and -not (Test-Path -LiteralPath (Join-Path $Destination $Name))) { throw "基础安装缺少更新目标：$Name" }
}

$StageRoot = [IO.Path]::GetFullPath((Join-Path $Destination ('.seedvr2-update-stage-' + [guid]::NewGuid().ToString('N'))))
$BackupBase = if ($IsTest) {
    [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $Destination) '.seedvr2-update-backups'))
} else {
    [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'SeedVR2 Upscaler\updates'))
}
$BackupRoot = [IO.Path]::GetFullPath((Join-Path $BackupBase ("$InstalledVersion-to-$($Manifest.version)-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8))))

if (-not $StageRoot.StartsWith($Destination + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw '无法创建安全的更新临时目录。'
}
if (-not $BackupRoot.StartsWith($BackupBase + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw '无法创建安全的更新备份目录。'
}

$ReplacementStarted = $false
try {
    New-Item -ItemType Directory -Force -Path $StageRoot, $BackupRoot | Out-Null
    foreach ($Name in $ManagedDirectories) {
        $Source = Join-Path $PayloadRoot $Name
        $Stage = Join-Path $StageRoot $Name
        New-Item -ItemType Directory -Force -Path $Stage | Out-Null
        & (Join-Path $env:SystemRoot 'System32\robocopy.exe') $Source $Stage /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NP | Out-Host
        if ($LASTEXITCODE -gt 7) { throw "暂存 $Name 失败：$LASTEXITCODE" }
    }
    foreach ($Name in $ManagedFiles) {
        Copy-Item -LiteralPath (Join-Path $PayloadRoot $Name) -Destination (Join-Path $StageRoot $Name) -Force
    }

    Write-Host "正在备份 $InstalledVersion…"
    foreach ($Name in $ManagedDirectories) {
        $Current = Join-Path $Destination $Name
        if (-not (Test-Path -LiteralPath $Current)) { continue }
        $Backup = Join-Path $BackupRoot $Name
        New-Item -ItemType Directory -Force -Path $Backup | Out-Null
        & (Join-Path $env:SystemRoot 'System32\robocopy.exe') $Current $Backup /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NP | Out-Host
        if ($LASTEXITCODE -gt 7) { throw "备份 $Name 失败：$LASTEXITCODE" }
    }
    foreach ($Name in $ManagedFiles) {
        Copy-Item -LiteralPath (Join-Path $Destination $Name) -Destination (Join-Path $BackupRoot $Name) -Force
    }

    Write-Host "正在安装 $($Manifest.version)…"
    $ReplacementStarted = $true
    foreach ($Name in $ManagedDirectories) {
        $Current = [IO.Path]::GetFullPath((Join-Path $Destination $Name))
        if (-not $Current.StartsWith($Destination + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw "拒绝替换安装目录外路径：$Current"
        }
        if (Test-Path -LiteralPath $Current) { Remove-Item -LiteralPath $Current -Recurse -Force }
        Move-Item -LiteralPath (Join-Path $StageRoot $Name) -Destination $Current
    }
    foreach ($Name in $ManagedFiles) {
        $Current = [IO.Path]::GetFullPath((Join-Path $Destination $Name))
        if (-not $Current.StartsWith($Destination + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw "拒绝替换安装目录外路径：$Current"
        }
        Remove-Item -LiteralPath $Current -Force
        Move-Item -LiteralPath (Join-Path $StageRoot $Name) -Destination $Current
    }

    if ($IsTest -and $env:SEEDVR2_UPDATE_TEST_FAIL_AFTER_REPLACE -eq '1') {
        throw '测试要求：替换后模拟失败。'
    }

    Write-Host '正在执行更新后 CUDA 自检…'
    Push-Location $Destination
    try {
        $env:PYTHONUTF8 = '1'
        $env:PYTHONIOENCODING = 'utf-8'
        $env:PYTHONNOUSERSITE = '1'
        $env:PYTHONDONTWRITEBYTECODE = '1'
        & (Join-Path $Destination 'runtime\python\python.exe') -B -m app.cli check --cuda
        if ($LASTEXITCODE -ne 0) { throw "更新后自检失败：$LASTEXITCODE" }
    } finally {
        Pop-Location
    }

    [ordered]@{
        fromVersion = $InstalledVersion
        toVersion = $Manifest.version
        installedAt = (Get-Date).ToString('o')
        destination = $Destination
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $BackupRoot 'update-report.json') -Encoding UTF8

    if (-not $IsTest) {
        try {
            $IconLocation = (Join-Path $Destination 'assets\seedvr2.ico') + ',0'
            $Shell = New-Object -ComObject WScript.Shell
            foreach ($ShortcutPath in @(
                (Join-Path ([Environment]::GetFolderPath('Desktop')) 'SeedVR2 图片放大工具.lnk'),
                (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\SeedVR2 图片放大工具\SeedVR2 图片放大工具.lnk')
            )) {
                if (Test-Path -LiteralPath $ShortcutPath) {
                    $Shortcut = $Shell.CreateShortcut($ShortcutPath)
                    $Shortcut.IconLocation = $IconLocation
                    $Shortcut.Save()
                }
            }
            $UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SeedVR2Upscaler'
            if (Test-Path -LiteralPath $UninstallKey) {
                New-ItemProperty -Path $UninstallKey -Name DisplayIcon -Value (Join-Path $Destination 'assets\seedvr2.ico') -PropertyType String -Force | Out-Null
                New-ItemProperty -Path $UninstallKey -Name DisplayVersion -Value $Manifest.version -PropertyType String -Force | Out-Null
            }
        } catch {
            Write-Warning "应用图标刷新失败，可重新运行完整安装器修复：$($_.Exception.Message)"
        }
    }
    Write-Host "SeedVR2 已更新到 $($Manifest.version)。旧代码备份位于：$BackupRoot"
} catch {
    if ($ReplacementStarted) {
        Write-Warning '更新失败，正在恢复旧代码…'
        foreach ($Name in $ManagedDirectories) {
            $Current = [IO.Path]::GetFullPath((Join-Path $Destination $Name))
            if ($Current.StartsWith($Destination + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $Current)) {
                Remove-Item -LiteralPath $Current -Recurse -Force
            }
            $Backup = Join-Path $BackupRoot $Name
            if (Test-Path -LiteralPath $Backup) { Move-Item -LiteralPath $Backup -Destination $Current }
        }
        foreach ($Name in $ManagedFiles) {
            $Current = [IO.Path]::GetFullPath((Join-Path $Destination $Name))
            if ($Current.StartsWith($Destination + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $Current)) {
                Remove-Item -LiteralPath $Current -Force
            }
            $Backup = Join-Path $BackupRoot $Name
            if (Test-Path -LiteralPath $Backup) { Move-Item -LiteralPath $Backup -Destination $Current }
        }
    }
    throw
} finally {
    if (Test-Path -LiteralPath $StageRoot) {
        Remove-Item -LiteralPath $StageRoot -Recurse -Force
    }
}
