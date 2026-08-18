param(
    [string]$Destination = '',
    [switch]$NoLaunch,
    [switch]$NoShortcuts
)

$ErrorActionPreference = 'Stop'
$Payload = Join-Path $PSScriptRoot 'payload'
$ManifestPath = Join-Path $PSScriptRoot 'release-manifest.json'

if (-not [Environment]::Is64BitOperatingSystem) {
    throw '仅支持 Windows x64。'
}
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw '发行清单缺失，安装包可能不完整。'
}
if (-not $Destination) {
    $Destination = $env:SEEDVR2_INSTALL_ROOT
}
if (-not $Destination) {
    $Destination = Join-Path $env:LOCALAPPDATA 'Programs\SeedVR2 Upscaler'
}
$Destination = [IO.Path]::GetFullPath($Destination)
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json

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

Write-Host '正在校验安装包关键文件…'
foreach ($Entry in $Manifest.criticalFiles) {
    $Path = Join-Path $Payload ($Entry.path -replace '/', '\')
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "安装包缺少文件：$($Entry.path)"
    }
    $File = Get-Item -LiteralPath $Path
    if ($File.Length -ne $Entry.bytes) {
        throw "文件大小不符：$($Entry.path)"
    }
    $Hash = Get-Sha256 $Path
    if ($Hash -ne $Entry.sha256) {
        throw "文件校验失败：$($Entry.path)"
    }
}

Write-Host '正在检查模型、Runtime 和 CUDA…'
Push-Location $Payload
try {
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & (Join-Path $Payload 'runtime\python\python.exe') -B -m app.cli check --cuda
    if ($LASTEXITCODE -ne 0) {
        throw "CUDA 自检失败，退出代码：$LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Write-Host "正在安装到：$Destination"
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
$RoboCopy = Join-Path $env:SystemRoot 'System32\robocopy.exe'
& $RoboCopy $Payload $Destination /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NP
if ($LASTEXITCODE -gt 7) {
    throw "复制安装文件失败，Robocopy 退出代码：$LASTEXITCODE"
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1') -Destination (Join-Path $Destination 'uninstall.ps1') -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '卸载 SeedVR2 放大工具.bat') -Destination (Join-Path $Destination '卸载 SeedVR2 放大工具.bat') -Force

Push-Location $Destination
try {
    & (Join-Path $Destination 'runtime\python\python.exe') -B -m app.cli check --cuda
    if ($LASTEXITCODE -ne 0) {
        throw "安装后自检失败，退出代码：$LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$IsTest = $env:SEEDVR2_RELEASE_TEST -eq '1'
if (-not $NoShortcuts -and -not $IsTest) {
    $Shell = New-Object -ComObject WScript.Shell
    $Desktop = [Environment]::GetFolderPath('Desktop')
    $StartMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\SeedVR2 图片放大工具'
    New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null

    foreach ($ShortcutPath in @(
        (Join-Path $Desktop 'SeedVR2 图片放大工具.lnk'),
        (Join-Path $StartMenu 'SeedVR2 图片放大工具.lnk')
    )) {
        $Shortcut = $Shell.CreateShortcut($ShortcutPath)
        $Shortcut.TargetPath = Join-Path $Destination 'runtime\python\pythonw.exe'
        $Shortcut.Arguments = '-B -s -m app.gui'
        $Shortcut.WorkingDirectory = $Destination
        $Shortcut.IconLocation = (Join-Path $Destination 'assets\seedvr2.ico') + ',0'
        $Shortcut.Save()
    }
    $UninstallShortcut = $Shell.CreateShortcut((Join-Path $StartMenu '卸载 SeedVR2 图片放大工具.lnk'))
    $UninstallShortcut.TargetPath = Join-Path $Destination '卸载 SeedVR2 放大工具.bat'
    $UninstallShortcut.WorkingDirectory = $Destination
    $UninstallShortcut.Save()

    $UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SeedVR2Upscaler'
    New-Item -Path $UninstallKey -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name DisplayName -Value 'SeedVR2 图片放大工具' -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name DisplayVersion -Value $Manifest.version -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name Publisher -Value 'SeedVR2 Upscaler' -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name InstallLocation -Value $Destination -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name DisplayIcon -Value (Join-Path $Destination 'assets\seedvr2.ico') -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name UninstallString -Value ('"' + (Join-Path $Destination '卸载 SeedVR2 放大工具.bat') + '"') -PropertyType String -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name EstimatedSize -Value ([int]($Manifest.payloadBytes / 1KB)) -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name NoModify -Value 1 -PropertyType DWord -Force | Out-Null
    New-ItemProperty -Path $UninstallKey -Name NoRepair -Value 1 -PropertyType DWord -Force | Out-Null
}

Write-Host 'SeedVR2 图片放大工具安装完成。'
if (-not $NoLaunch -and -not $IsTest) {
    Start-Process -FilePath (Join-Path $Destination 'runtime\python\pythonw.exe') -ArgumentList '-B', '-s', '-m', 'app.gui' -WorkingDirectory $Destination
}
