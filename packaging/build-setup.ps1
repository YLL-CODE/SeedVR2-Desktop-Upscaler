param([string]$Version = '')

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if (-not $Version) { $Version = (Get-Content -LiteralPath (Join-Path $ProjectRoot 'VERSION') -Raw).Trim() }
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "版本号格式无效：$Version" }

$WorkspaceRoot = [IO.Path]::GetFullPath((Split-Path -Parent $ProjectRoot))
$ToolRoot = Join-Path $WorkspaceRoot '.release-tools\inno-7.0.2'
$ToolInstaller = Join-Path $ToolRoot 'innosetup-7.0.2-x64.exe'
$CompilerRoot = Join-Path $ToolRoot 'compiler'
$Compiler = Join-Path $CompilerRoot 'ISCC.exe'
$BuildRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '.setup-build'))
$Payload = Join-Path $BuildRoot 'payload'
$ReleaseRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot "dist\SeedVR2-Upscaler-$Version-win-x64-setup"))

foreach ($Path in @($BuildRoot, $ReleaseRoot)) {
    if (-not $Path.StartsWith($ProjectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝清理项目外目录：$Path"
    }
}

if (-not (Test-Path -LiteralPath $Compiler -PathType Leaf)) {
    New-Item -ItemType Directory -Force -Path $ToolRoot | Out-Null
    if (-not (Test-Path -LiteralPath $ToolInstaller -PathType Leaf)) {
        Invoke-WebRequest -Uri 'https://github.com/jrsoftware/issrc/releases/download/is-7_0_2/innosetup-7.0.2-x64.exe' -OutFile $ToolInstaller
    }
    $Signature = Get-AuthenticodeSignature -LiteralPath $ToolInstaller
    if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'Pyrsys B\.V\.') {
        throw 'Inno Setup 构建工具数字签名验证失败。'
    }
    New-Item -ItemType Directory -Force -Path $CompilerRoot | Out-Null
    $Arguments = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CURRENTUSER', '/PORTABLE=1', ('/DIR="' + $CompilerRoot + '"'))
    $Process = Start-Process -FilePath $ToolInstaller -ArgumentList $Arguments -WindowStyle Hidden -Wait -PassThru
    if ($Process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $Compiler -PathType Leaf)) {
        throw "Inno Setup 构建工具安装失败：$($Process.ExitCode)"
    }
}

$CompilerSignature = Get-AuthenticodeSignature -LiteralPath $Compiler
if ($CompilerSignature.Status -ne 'Valid' -or $CompilerSignature.SignerCertificate.Subject -notmatch 'Pyrsys B\.V\.') {
    throw "Inno Setup compiler signature verification failed: $($CompilerSignature.Status)"
}

if (Test-Path -LiteralPath $BuildRoot) { Remove-Item -LiteralPath $BuildRoot -Recurse -Force }
if (Test-Path -LiteralPath $ReleaseRoot) { Remove-Item -LiteralPath $ReleaseRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Payload, $ReleaseRoot | Out-Null

function Copy-Tree([string]$Name) {
    $Source = Join-Path $ProjectRoot $Name
    $Target = Join-Path $Payload $Name
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    & (Join-Path $env:SystemRoot 'System32\robocopy.exe') $Source $Target /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /XD __pycache__ /XF '*.pyc' /NFL /NDL /NP | Out-Host
    if ($LASTEXITCODE -gt 7) { throw "复制 $Name 失败：$LASTEXITCODE" }
}

Write-Host '正在建立标准安装器的干净 payload…'
foreach ($Name in @('app', 'assets', 'vendor', 'runtime', 'models')) { Copy-Tree $Name }
foreach ($Name in @('README.md', 'README_EN.md', 'CHANGELOG.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'requirements-lock.txt', 'VERSION', '启动 SeedVR2 放大工具.bat')) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Name) -Destination (Join-Path $Payload $Name) -Force
}

$CriticalRelativePaths = @(
    'models/SEEDVR2/seedvr2_ema_7b_sharp-Q4_K_M.gguf',
    'models/SEEDVR2/ema_vae_fp16.safetensors',
    'runtime/python/python.exe',
    'assets/seedvr2.ico',
    'app/gui.py',
    'app/worker.py',
    'vendor/seedvr2/LICENSE'
)
$Critical = foreach ($Relative in $CriticalRelativePaths) {
    $Path = Join-Path $Payload ($Relative -replace '/', '\')
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "发行文件缺失：$Relative" }
    $File = Get-Item -LiteralPath $Path
    [ordered]@{ path = $Relative; bytes = $File.Length; sha256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash }
}
$PayloadFiles = Get-ChildItem -LiteralPath $Payload -Recurse -File -Force
[ordered]@{
    product = 'SeedVR2 Upscaler'
    version = $Version
    channel = 'public-github-windows-x64-setup'
    payloadFiles = $PayloadFiles.Count
    payloadBytes = ($PayloadFiles | Measure-Object Length -Sum).Sum
    containsModels = $true
    containsSensitiveData = $false
    criticalFiles = @($Critical)
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Payload 'release-manifest.json') -Encoding UTF8

Write-Host '正在执行发行隐私扫描…'
$ForbiddenNames = Get-ChildItem -LiteralPath $Payload -Recurse -File -Force | Where-Object {
    $IsPublicCaBundle = $_.Name -eq 'cacert.pem' -and $_.FullName -match '\\site-packages\\(?:pip\\_vendor\\)?certifi\\cacert\.pem$'
    -not $IsPublicCaBundle -and $_.Name -match '^(\.env|credentials.*|.*\.(pem|key|db))$'
}
if ($ForbiddenNames) { throw '发行 payload 包含禁止的敏感文件名。' }
$TextFiles = Get-ChildItem -LiteralPath $Payload -Recurse -File -Force | Where-Object {
    $_.Extension -in @('.py', '.ps1', '.cmd', '.bat', '.txt', '.md', '.json', '.yaml', '.yml', '.pth', '.cfg', '.ini')
}
$LocalRoots = @($env:USERPROFILE, $env:LOCALAPPDATA, $env:TEMP, $WorkspaceRoot) |
    Where-Object { $_ } |
    ForEach-Object { [Regex]::Escape([IO.Path]::GetFullPath($_).TrimEnd('\')) }
$ForbiddenPattern = ('(?i)(?:' + ($LocalRoots -join '|') + '|[A-Z]:\\AIGC\\|sk-' + 'ant-|sk-' + 'proj-|OPENAI_' + 'API_KEY|ANTHROPIC_' + 'API_KEY)')
foreach ($File in $TextFiles) {
    if (Select-String -LiteralPath $File.FullName -Pattern $ForbiddenPattern -Quiet) {
        throw "发行隐私扫描失败：$($File.FullName.Substring($Payload.Length + 1))"
    }
}

Write-Host '正在验证 payload Runtime、模型和 CUDA…'
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

Write-Host '正在编译标准 Windows 安装器，这一步可能需要数分钟…'
& $Compiler "/DSourceRoot=$Payload" "/DAppVersion=$Version" "/DOutputDir=$ReleaseRoot" (Join-Path $PSScriptRoot 'SeedVR2-Setup.iss')
if ($LASTEXITCODE -ne 0) { throw "Inno Setup 编译失败：$LASTEXITCODE" }

Copy-Item -LiteralPath (Join-Path $PSScriptRoot '安装说明.txt') -Destination $ReleaseRoot -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Installation Guide.txt') -Destination $ReleaseRoot -Force
$SetupExe = Join-Path $ReleaseRoot "SeedVR2-Setup-$Version.exe"
if (-not (Test-Path -LiteralPath $SetupExe -PathType Leaf)) { throw "安装入口缺失：$SetupExe" }
$ReleaseFiles = Get-ChildItem -LiteralPath $ReleaseRoot -File -Force
[ordered]@{
    installer = Split-Path -Leaf $SetupExe
    distribution = Split-Path -Leaf $ReleaseRoot
    version = $Version
    bytes = ($ReleaseFiles | Measure-Object Length -Sum).Sum
    signed = (Get-AuthenticodeSignature -LiteralPath $SetupExe).Status -eq 'Valid'
    files = @($ReleaseFiles | Sort-Object Name | ForEach-Object {
        [ordered]@{ name = $_.Name; bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
    })
    payloadFiles = $PayloadFiles.Count + 1
    payloadBytes = (Get-ChildItem -LiteralPath $Payload -Recurse -File -Force | Measure-Object Length -Sum).Sum
    containsSensitiveData = $false
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $ReleaseRoot 'release-summary.json') -Encoding UTF8

$Checksums = foreach ($File in (Get-ChildItem -LiteralPath $ReleaseRoot -File -Force | Sort-Object Name)) {
    "{0}  {1}" -f (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash, $File.Name
}
$Checksums | Set-Content -LiteralPath (Join-Path $ReleaseRoot 'SHA256SUMS.txt') -Encoding UTF8

Write-Host "标准安装包已生成：$ReleaseRoot"
