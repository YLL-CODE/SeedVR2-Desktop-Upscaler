param([Parameter(ValueFromRemainingArguments = $true)][string[]]$InstallArguments)

$ErrorActionPreference = 'Stop'
$PackageRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$SevenZip = Join-Path $PackageRoot 'tools\7za.exe'
$FirstVolume = Join-Path $PackageRoot 'payload.7z.001'
$TempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$TempRoot = [IO.Path]::GetFullPath((Join-Path $TempBase ('SeedVR2Installer-' + [guid]::NewGuid().ToString('N'))))

if (-not (Test-Path -LiteralPath $SevenZip -PathType Leaf)) { throw '安装工具缺失：tools\7za.exe' }
if (-not (Test-Path -LiteralPath $FirstVolume -PathType Leaf)) { throw '安装数据缺失：payload.7z.001' }
if (-not $TempRoot.StartsWith($TempBase, [StringComparison]::OrdinalIgnoreCase)) { throw '无法创建安全临时目录。' }

New-Item -ItemType Directory -Force -Path $TempRoot | Out-Null
try {
    Write-Host '正在解压 SeedVR2 离线安装数据…'
    & $SevenZip x -y $FirstVolume ("-o$TempRoot")
    if ($LASTEXITCODE -ne 0) { throw "安装数据解压失败：$LASTEXITCODE" }
    Copy-Item -LiteralPath (Join-Path $PackageRoot 'install.ps1') -Destination (Join-Path $TempRoot 'install.ps1') -Force
    $Installer = Join-Path $TempRoot 'install.ps1'
    if (-not (Test-Path -LiteralPath $Installer -PathType Leaf)) { throw '安装脚本缺失。' }
    & (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe') `
        -NoLogo -NoProfile -ExecutionPolicy Bypass -File $Installer @InstallArguments
    if ($LASTEXITCODE -ne 0) { throw "安装失败：$LASTEXITCODE" }
} finally {
    if (Test-Path -LiteralPath $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force
    }
}
