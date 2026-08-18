param(
    [string]$Version = '',
    [string]$CompatibleVersions = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
if (-not $Version) { $Version = (Get-Content -LiteralPath (Join-Path $ProjectRoot 'VERSION') -Raw).Trim() }
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "版本号格式无效：$Version" }
if (-not $CompatibleVersions) { $CompatibleVersions = $Version }
$Compatible = @($CompatibleVersions.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($Compatible.Count -eq 0 -or @($Compatible | Where-Object { $_ -notmatch '^\d+\.\d+\.\d+$' }).Count -gt 0) {
    throw '兼容版本列表格式无效，请使用逗号分隔的语义版本号。'
}

$DistRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'dist'))
$ReleaseRoot = [IO.Path]::GetFullPath((Join-Path $DistRoot "SeedVR2-Upscaler-$Version-code-update"))
$PayloadRoot = Join-Path $ReleaseRoot 'payload'
if (-not $ReleaseRoot.StartsWith($ProjectRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "拒绝清理项目外目录：$ReleaseRoot"
}
if (Test-Path -LiteralPath $ReleaseRoot) { Remove-Item -LiteralPath $ReleaseRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $PayloadRoot | Out-Null

function Copy-Tree([string]$Name) {
    $Source = Join-Path $ProjectRoot $Name
    $Target = Join-Path $PayloadRoot $Name
    New-Item -ItemType Directory -Force -Path $Target | Out-Null
    & (Join-Path $env:SystemRoot 'System32\robocopy.exe') $Source $Target /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /XD __pycache__ /XF '*.pyc' /NFL /NDL /NP | Out-Host
    if ($LASTEXITCODE -gt 7) { throw "复制 $Name 失败：$LASTEXITCODE" }
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

Write-Host '正在建立小型代码更新 payload…'
foreach ($Name in @('app', 'assets', 'vendor')) { Copy-Tree $Name }
foreach ($Name in @('README.md', 'VERSION', '启动 SeedVR2 放大工具.bat')) {
    Copy-Item -LiteralPath (Join-Path $ProjectRoot $Name) -Destination (Join-Path $PayloadRoot $Name) -Force
}
foreach ($Name in @('Install-Update.cmd', 'install-update.ps1', '更新说明.txt')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $Name) -Destination (Join-Path $ReleaseRoot $Name) -Force
}

$RuntimeLockHash = Get-RequirementsHash (Join-Path $ProjectRoot 'requirements-lock.txt')
$Files = @(
    Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File | Sort-Object FullName | ForEach-Object {
        [ordered]@{
            path = $_.FullName.Substring($PayloadRoot.Length + 1).Replace('\', '/')
            bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        }
    }
)
$Manifest = [ordered]@{
    schemaVersion = 1
    version = $Version
    compatibleInstalledVersions = $Compatible
    runtimeLockSha256 = $RuntimeLockHash
    managedDirectories = @('app', 'assets', 'vendor')
    managedFiles = @('README.md', 'VERSION', '启动 SeedVR2 放大工具.bat')
    models = @(
        [ordered]@{ path = 'models/SEEDVR2/seedvr2_ema_7b_sharp-Q4_K_M.gguf'; bytes = 4758306592 },
        [ordered]@{ path = 'models/SEEDVR2/ema_vae_fp16.safetensors'; bytes = 501324814 }
    )
    files = $Files
}
$Manifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $ReleaseRoot 'update-manifest.json') -Encoding UTF8

$SecretPatterns = ('C:\\Users\\|AppData\\Local\\Temp|sk-' + 'proj-|sk-' + 'ant-|OPENAI_' + 'API_KEY\s*=|ANTHROPIC_' + 'API_KEY\s*=|BEGIN (RSA |EC |OPENSSH )?PRIVATE ' + 'KEY')
$TextFiles = Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File | Where-Object { $_.Extension -in @('.py', '.ps1', '.cmd', '.bat', '.md', '.txt', '.json', '.yaml', '.yml') }
$PrivacyHits = @($TextFiles | Select-String -Pattern $SecretPatterns)
if ($PrivacyHits.Count -gt 0) { throw '代码更新包隐私扫描失败。' }

$HashLines = foreach ($File in (Get-ChildItem -LiteralPath $ReleaseRoot -Recurse -File | Sort-Object FullName)) {
    $Relative = $File.FullName.Substring($ReleaseRoot.Length + 1).Replace('\', '/')
    '{0}  {1}' -f (Get-FileHash -LiteralPath $File.FullName -Algorithm SHA256).Hash, $Relative
}
$HashLines | Set-Content -LiteralPath (Join-Path $ReleaseRoot 'SHA256SUMS.txt') -Encoding UTF8

$Bytes = (Get-ChildItem -LiteralPath $ReleaseRoot -Recurse -File | Measure-Object Length -Sum).Sum
Write-Host "代码更新包已生成：$ReleaseRoot"
Write-Host "总大小：$Bytes 字节"
