param([switch]$Quiet)

$ErrorActionPreference = 'Stop'
$InstallRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$ExpectedParent = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs'))
$IsTest = $env:SEEDVR2_RELEASE_TEST -eq '1'
$UninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\SeedVR2Upscaler'
$RegisteredInstall = Get-ItemPropertyValue -LiteralPath $UninstallKey -Name InstallLocation -ErrorAction SilentlyContinue
$RegisteredRoot = if ($RegisteredInstall) { [IO.Path]::GetFullPath($RegisteredInstall) } else { '' }
$IsDefaultLocation = $InstallRoot.StartsWith($ExpectedParent + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
$IsRegisteredLocation = $RegisteredRoot -and $InstallRoot.TrimEnd('\') -eq $RegisteredRoot.TrimEnd('\')

if (-not $IsTest -and -not $IsDefaultLocation -and -not $IsRegisteredLocation) {
    throw "拒绝删除未登记的安装目录：$InstallRoot"
}
if (-not $Quiet -and -not $IsTest) {
    Add-Type -AssemblyName PresentationFramework
    $Choice = [System.Windows.MessageBox]::Show(
        '确认卸载 SeedVR2 图片放大工具？原始图片和输出目录不会删除。',
        '卸载 SeedVR2 图片放大工具',
        'YesNo',
        'Question'
    )
    if ($Choice -ne 'Yes') { exit 0 }
}

if (-not $IsTest) {
    $DesktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'SeedVR2 图片放大工具.lnk'
    $StartMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\SeedVR2 图片放大工具'
    Remove-Item -LiteralPath $DesktopShortcut -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $StartMenu -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $UninstallKey -Recurse -Force -ErrorAction SilentlyContinue
}

Set-Location ([IO.Path]::GetTempPath())
Remove-Item -LiteralPath $InstallRoot -Recurse -Force
