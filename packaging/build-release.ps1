param([string]$Version = '')

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if (-not $Version) {
    $Version = (Get-Content -LiteralPath (Join-Path $ProjectRoot 'VERSION') -Raw).Trim()
}
if ($Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "版本号格式无效：$Version"
}

$WorkspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $ProjectRoot))
$ToolRoot = Join-Path $WorkspaceRoot '.release-tools'
$Tar = Join-Path $env:SystemRoot 'System32\tar.exe'
$PackageSevenZip = Join-Path $ToolRoot 'extra\x64\7za.exe'
$SevenZipLicense = Join-Path $ToolRoot 'extra\License.txt'
$SevenZipExtra = Join-Path $ToolRoot '7z2602-extra.7z'
$BuildRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '.release-build'))
$DistRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'dist'))
$PackageRoot = Join-Path $BuildRoot "SeedVR2-Upscaler-$Version"
$Payload = Join-Path $PackageRoot 'payload'
$ReleaseRoot = [IO.Path]::GetFullPath((Join-Path $DistRoot "SeedVR2-Upscaler-$Version-win-x64-private"))
$Archive = Join-Path $ReleaseRoot 'payload.7z'

if (-not (Test-Path -LiteralPath $PackageSevenZip -PathType Leaf)) {
    New-Item -ItemType Directory -Force -Path $ToolRoot | Out-Null
    if (-not (Test-Path -LiteralPath $SevenZipExtra)) {
        Invoke-WebRequest -Uri 'https://www.7-zip.org/a/7z2602-extra.7z' -OutFile $SevenZipExtra
    }
    if ((Get-FileHash -LiteralPath $SevenZipExtra -Algorithm SHA256).Hash -ne '081DF9E9311DFD9C9E0E98C1C80180B99BB51E4CB24156B5F3057FE3C259D70A') {
        throw '7-Zip 26.02 Extra SHA256 mismatch.'
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $ToolRoot 'extra') | Out-Null
    & $Tar -xf $SevenZipExtra -C (Join-Path $ToolRoot 'extra')
    if ($LASTEXITCODE -ne 0) { throw "7-Zip Extra extraction failed: $LASTEXITCODE" }
}

foreach ($Required in @($Tar, $PackageSevenZip, $SevenZipLicense)) {
    if (-not (Test-Path -LiteralPath $Required -PathType Leaf)) {
        throw "缺少发行构建工具：$Required"
    }
}
foreach ($Path in @($BuildRoot, $DistRoot, $ReleaseRoot)) {
    if (-not $Path.StartsWith($ProjectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝清理工作区外目录：$Path"
    }
}

if (Test-Path -LiteralPath $BuildRoot) { Remove-Item -LiteralPath $BuildRoot -Recurse -Force }
if (Test-Path -LiteralPath $ReleaseRoot) { Remove-Item -LiteralPath $ReleaseRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Payload, (Join-Path $ReleaseRoot 'tools') | Out-Null

function Copy-Tree([string]$Name) {
    $Source = Join-Path $ProjectRoot $Name
    $Target = Join-Path $Payload $Name
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    & (Join-Path $env:SystemRoot 'System32\robocopy.exe') $Source $Target /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /XD __pycache__ /XF '*.pyc' /NFL /NDL /NP | Out-Host
    if ($LASTEXITCODE -gt 7) { throw "复制 $Name 失败，Robocopy 退出代码：$LASTEXITCODE" }
}

Write-Host '正在建立去缓存发行 payload…'
foreach ($Name in @('app', 'assets', 'vendor', 'runtime', 'models')) { Copy-Tree $Name }
foreach ($Name in @('README.md', 'requirements-lock.txt', 'VERSION', '启动 SeedVR2 放大工具.bat')) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Name) -Destination (Join-Path $Payload $Name) -Force
}
foreach ($Name in @('install.ps1', 'uninstall.ps1', '卸载 SeedVR2 放大工具.bat', '安装说明.txt')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $Name) -Destination (Join-Path $PackageRoot $Name) -Force
}

$CriticalRelativePaths = @(
    'models/SEEDVR2/seedvr2_ema_7b_sharp-Q4_K_M.gguf',
    'models/SEEDVR2/ema_vae_fp16.safetensors',
    'runtime/python/python.exe',
    'assets/seedvr2.ico',
    'app/worker.py',
    'app/pipeline.py',
    'vendor/seedvr2/LICENSE'
)
$Critical = foreach ($Relative in $CriticalRelativePaths) {
    $Path = Join-Path $Payload ($Relative -replace '/', '\')
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "发行文件缺失：$Relative" }
    $File = Get-Item -LiteralPath $Path
    [ordered]@{ path = $Relative; bytes = $File.Length; sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
}
$PayloadFiles = Get-ChildItem -LiteralPath $Payload -Recurse -File -Force
$Manifest = [ordered]@{
    product = 'SeedVR2 Upscaler'
    version = $Version
    channel = 'private-offline-windows-x64'
    payloadFiles = $PayloadFiles.Count
    payloadBytes = ($PayloadFiles | Measure-Object Length -Sum).Sum
    containsModels = $true
    containsSensitiveData = $false
    criticalFiles = @($Critical)
}
$Manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PackageRoot 'release-manifest.json') -Encoding UTF8

Write-Host '正在执行发行隐私扫描…'
$ForbiddenNames = Get-ChildItem -LiteralPath $PackageRoot -Recurse -File -Force | Where-Object {
    $IsPublicCaBundle = $_.Name -eq 'cacert.pem' -and $_.FullName -match '\\site-packages\\(?:pip\\_vendor\\)?certifi\\cacert\.pem$'
    -not $IsPublicCaBundle -and $_.Name -match '^(\.env|credentials.*|.*\.(pem|key|db))$'
}
if ($ForbiddenNames) { throw '发行 payload 包含禁止的敏感文件名。' }
$TextFiles = Get-ChildItem -LiteralPath $PackageRoot -Recurse -File -Force | Where-Object {
    $_.Extension -in @('.py', '.ps1', '.cmd', '.bat', '.txt', '.md', '.json', '.yaml', '.yml', '.pth', '.cfg', '.ini')
}
$LocalRoots = @($env:USERPROFILE, $env:LOCALAPPDATA, $env:TEMP, $WorkspaceRoot) |
    Where-Object { $_ } |
    ForEach-Object { [Regex]::Escape([IO.Path]::GetFullPath($_).TrimEnd('\')) }
$ForbiddenPattern = ('(?i)(?:' + ($LocalRoots -join '|') + '|[A-Z]:\\AIGC\\|sk-' + 'ant-|sk-' + 'proj-|OPENAI_' + 'API_KEY|ANTHROPIC_' + 'API_KEY)')
foreach ($File in $TextFiles) {
    if (Select-String -LiteralPath $File.FullName -Pattern $ForbiddenPattern -Quiet) {
        throw "发行隐私扫描失败：$($File.FullName.Substring($PackageRoot.Length + 1))"
    }
}

Write-Host '正在验证可迁移 Runtime…'
Push-Location $Payload
try {
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONNOUSERSITE = '1'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & (Join-Path $Payload 'runtime\python\python.exe') -B -m app.cli check --cuda
    if ($LASTEXITCODE -ne 0) { throw "发行 payload 自检失败：$LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host '正在压缩离线 payload，这一步可能需要数分钟…'
Push-Location $PackageRoot
try {
    & $PackageSevenZip a -t7z $Archive '*' -m0=lzma2 -mx=5 -md=64m -mmt=on -ms=on -v1900m
    if ($LASTEXITCODE -ne 0) { throw "7-Zip 压缩失败：$LASTEXITCODE" }
} finally {
    Pop-Location
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Install-SeedVR2.cmd') -Destination $ReleaseRoot -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'package-install.ps1') -Destination $ReleaseRoot -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'install.ps1') -Destination $ReleaseRoot -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '安装说明.txt') -Destination $ReleaseRoot -Force
Copy-Item -LiteralPath $PackageSevenZip -Destination (Join-Path $ReleaseRoot 'tools\7za.exe') -Force
Copy-Item -LiteralPath $SevenZipLicense -Destination (Join-Path $ReleaseRoot 'tools\7-Zip-License.txt') -Force

$VolumeFiles = Get-ChildItem -LiteralPath $ReleaseRoot -File -Filter 'payload.7z.*' | Sort-Object Name
$ReleaseFiles = Get-ChildItem -LiteralPath $ReleaseRoot -Recurse -File -Force
[ordered]@{
    installer = 'Install-SeedVR2.cmd'
    distribution = Split-Path -Leaf $ReleaseRoot
    bytes = ($ReleaseFiles | Measure-Object Length -Sum).Sum
    signed = $false
    volumes = @($VolumeFiles | ForEach-Object { [ordered]@{ name = $_.Name; bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash } })
    payloadFiles = $Manifest.payloadFiles
    payloadBytes = $Manifest.payloadBytes
    containsSensitiveData = $false
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $ReleaseRoot 'release-summary.json') -Encoding UTF8
$ReleaseFiles = Get-ChildItem -LiteralPath $ReleaseRoot -Recurse -File -Force
$Checksums = foreach ($File in $ReleaseFiles) {
    $Relative = $File.FullName.Substring($ReleaseRoot.Length + 1).Replace('\', '/')
    "{0}  {1}" -f (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash, $Relative
}
$Checksums | Set-Content -LiteralPath (Join-Path $ReleaseRoot 'SHA256SUMS.txt') -Encoding UTF8

Write-Host "发行包已生成：$ReleaseRoot"
Write-Host "数据分卷：$($VolumeFiles.Count) 个"
