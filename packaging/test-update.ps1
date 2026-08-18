param(
    [string]$PackageRoot = '',
    [string]$InstalledRoot = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$Version = (Get-Content -LiteralPath (Join-Path $ProjectRoot 'VERSION') -Raw).Trim()
if (-not $PackageRoot) {
    $PackageRoot = Join-Path $ProjectRoot "dist\SeedVR2-Upscaler-$Version-code-update"
}
if (-not $InstalledRoot) {
    $InstalledRoot = Join-Path $env:LOCALAPPDATA 'Programs\SeedVR2 Upscaler'
}
$PackageRoot = [IO.Path]::GetFullPath($PackageRoot)
$InstalledRoot = [IO.Path]::GetFullPath($InstalledRoot)
$TmpBase = [IO.Path]::GetFullPath((Join-Path $ProjectRoot '.tmp'))
$TestRoot = [IO.Path]::GetFullPath((Join-Path $TmpBase ("update-$Version-" + [guid]::NewGuid().ToString('N'))))

if (-not $TestRoot.StartsWith($TmpBase + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Update test directory escaped the project temp root.'
}
foreach ($Required in @(
    (Join-Path $PackageRoot 'install-update.ps1'),
    (Join-Path $PackageRoot 'update-manifest.json'),
    (Join-Path $InstalledRoot 'runtime\python\python.exe'),
    (Join-Path $InstalledRoot 'models'),
    (Join-Path $InstalledRoot 'app')
)) {
    if (-not (Test-Path -LiteralPath $Required)) { throw "Missing update test dependency: $Required" }
}
$Launcher = Get-ChildItem -LiteralPath $InstalledRoot -File -Filter '*.bat' |
    Where-Object { Select-String -LiteralPath $_.FullName -Pattern 'pythonw\.exe' -Quiet } |
    Select-Object -First 1
if (-not $Launcher) { throw 'Cannot find the installed GUI launcher.' }

function Copy-Tree([string]$Source, [string]$Destination) {
    & (Join-Path $env:SystemRoot 'System32\robocopy.exe') $Source $Destination /E /COPY:DAT /DCOPY:DAT /R:2 /W:1 /XJ /NFL /NDL /NP | Out-Null
    if ($LASTEXITCODE -gt 7) { throw "Test install copy failed: $Source ($LASTEXITCODE)" }
}

function New-TestInstall([string]$Destination) {
    New-Item -ItemType Directory -Force -Path $Destination | Out-Null
    foreach ($Directory in @('app', 'vendor')) {
        Copy-Tree (Join-Path $InstalledRoot $Directory) (Join-Path $Destination $Directory)
    }
    foreach ($File in @('README.md', 'VERSION', 'requirements-lock.txt')) {
        Copy-Item -LiteralPath (Join-Path $InstalledRoot $File) -Destination (Join-Path $Destination $File) -Force
    }
    Copy-Item -LiteralPath $Launcher.FullName -Destination (Join-Path $Destination $Launcher.Name) -Force
    New-Item -ItemType Junction -Path (Join-Path $Destination 'runtime') -Target (Join-Path $InstalledRoot 'runtime') | Out-Null
    New-Item -ItemType Junction -Path (Join-Path $Destination 'models') -Target (Join-Path $InstalledRoot 'models') | Out-Null
}

function Remove-TestRoot([string]$Root) {
    $Root = [IO.Path]::GetFullPath($Root)
    if (-not $Root.StartsWith($TmpBase + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Refusing to clean an unverified update test directory.'
    }
    foreach ($Destination in @((Join-Path $Root 'success'), (Join-Path $Root 'rollback'))) {
        foreach ($LinkName in @('runtime', 'models')) {
            $Link = Join-Path $Destination $LinkName
            if (Test-Path -LiteralPath $Link) {
                $Item = Get-Item -LiteralPath $Link -Force
                if (-not ($Item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                    throw "Refusing to unlink a non-junction test path: $Link"
                }
                [IO.Directory]::Delete($Link, $false)
            }
        }
    }
    if (Test-Path -LiteralPath $Root) { Remove-Item -LiteralPath $Root -Recurse -Force }
}

if (Test-Path -LiteralPath $TmpBase) {
    foreach ($StaleRoot in (Get-ChildItem -LiteralPath $TmpBase -Directory -Filter "update-$Version-*")) {
        Remove-TestRoot $StaleRoot.FullName
    }
}

$Success = Join-Path $TestRoot 'success'
$Rollback = Join-Path $TestRoot 'rollback'
try {
    New-Item -ItemType Directory -Force -Path $TestRoot | Out-Null
    New-TestInstall $Success
    New-TestInstall $Rollback

    $RollbackVersionBefore = (Get-Content -LiteralPath (Join-Path $Rollback 'VERSION') -Raw).Trim()
    $RollbackGuiBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Rollback 'app\gui.py')).Hash

    $env:SEEDVR2_RELEASE_TEST = '1'
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PackageRoot 'install-update.ps1') -Destination $Success
    $SuccessExit = $LASTEXITCODE
    if ($SuccessExit -ne 0) { throw "Successful update path failed: $SuccessExit" }

    $SuccessVersion = (Get-Content -LiteralPath (Join-Path $Success 'VERSION') -Raw).Trim()
    $PayloadGuiHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PackageRoot 'payload\app\gui.py')).Hash
    $SuccessGuiHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Success 'app\gui.py')).Hash
    $PayloadIconHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PackageRoot 'payload\assets\seedvr2.ico')).Hash
    $SuccessIconHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Success 'assets\seedvr2.ico')).Hash
    & (Join-Path $Success 'runtime\python\python.exe') -B -s -m app.gui --smoke-test
    $SmokeExit = $LASTEXITCODE

    $env:SEEDVR2_UPDATE_TEST_FAIL_AFTER_REPLACE = '1'
    & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PackageRoot 'install-update.ps1') -Destination $Rollback
    $RollbackExit = $LASTEXITCODE
    Remove-Item Env:SEEDVR2_UPDATE_TEST_FAIL_AFTER_REPLACE -ErrorAction SilentlyContinue

    $RollbackVersionAfter = (Get-Content -LiteralPath (Join-Path $Rollback 'VERSION') -Raw).Trim()
    $RollbackGuiAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Rollback 'app\gui.py')).Hash
    $Result = [pscustomobject]@{
        SuccessUpdateExit = $SuccessExit
        SuccessVersion = $SuccessVersion
        PayloadHashMatched = $PayloadGuiHash -eq $SuccessGuiHash
        IconHashMatched = $PayloadIconHash -eq $SuccessIconHash
        GuiSmokeExit = $SmokeExit
        ForcedFailureExit = $RollbackExit
        RollbackVersionRestored = $RollbackVersionAfter -eq $RollbackVersionBefore
        RollbackGuiRestored = $RollbackGuiAfter -eq $RollbackGuiBefore
        RollbackRemovedNewAssets = -not (Test-Path -LiteralPath (Join-Path $Rollback 'assets'))
    }
    $Result | Format-List

    if (
        $SuccessVersion -ne $Version -or
        $PayloadGuiHash -ne $SuccessGuiHash -or
        $PayloadIconHash -ne $SuccessIconHash -or
        $SmokeExit -ne 0 -or
        $RollbackExit -eq 0 -or
        $RollbackVersionAfter -ne $RollbackVersionBefore -or
        $RollbackGuiAfter -ne $RollbackGuiBefore -or
        (Test-Path -LiteralPath (Join-Path $Rollback 'assets'))
    ) {
        throw 'Isolated update validation failed.'
    }
} finally {
    Remove-Item Env:SEEDVR2_UPDATE_TEST_FAIL_AFTER_REPLACE -ErrorAction SilentlyContinue
    Remove-Item Env:SEEDVR2_RELEASE_TEST -ErrorAction SilentlyContinue
    Remove-TestRoot $TestRoot
}
