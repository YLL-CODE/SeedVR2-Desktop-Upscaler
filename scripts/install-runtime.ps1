$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $ProjectRoot 'runtime\python'
$DownloadRoot = Join-Path $ProjectRoot '.downloads'
$Installer = Join-Path $DownloadRoot 'python-3.13.6-amd64.exe'
$Python = Join-Path $RuntimeRoot 'python.exe'
$PythonUrl = 'https://www.python.org/ftp/python/3.13.6/python-3.13.6-amd64.exe'
$PythonInstallerSha256 = '5EDCE6F0597A9B250C72790DC076649B06C1DC4754F3C68D7C284A1F10C33F36'

New-Item -ItemType Directory -Force -Path $DownloadRoot | Out-Null
if (-not (Test-Path -LiteralPath $Python)) {
    if (-not (Test-Path -LiteralPath $Installer)) {
        Write-Host 'Downloading official CPython 3.13.6 installer...'
        Invoke-WebRequest -Uri $PythonUrl -OutFile $Installer
    }
    $ActualHash = (Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash
    if ($ActualHash -ne $PythonInstallerSha256) { throw "Python installer SHA256 mismatch: $ActualHash" }
    $Signature = Get-AuthenticodeSignature -LiteralPath $Installer
    if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
        throw "Python installer signature is not valid: $($Signature.StatusMessage)"
    }
    Write-Host "Installing clean Python runtime at $RuntimeRoot ..."
    $Arguments = @(
        '/quiet',
        'InstallAllUsers=0',
        "TargetDir=$RuntimeRoot",
        'Include_launcher=0',
        'AssociateFiles=0',
        'Shortcuts=0',
        'PrependPath=0',
        'Include_doc=0',
        'Include_test=0',
        'Include_tcltk=1',
        'Include_pip=1'
    )
    $Process = Start-Process -FilePath $Installer -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden
    if ($Process.ExitCode -ne 0) { throw "Python installer failed with exit code $($Process.ExitCode)." }
}

& $Python -m pip install --disable-pip-version-check --upgrade 'pip==25.2'
if ($LASTEXITCODE -ne 0) { throw "pip bootstrap failed with exit code $LASTEXITCODE." }
& $Python -m pip install --disable-pip-version-check `
    -r (Join-Path $ProjectRoot 'requirements-lock.txt') `
    --extra-index-url 'https://download.pytorch.org/whl/cu130'
if ($LASTEXITCODE -ne 0) { throw "Runtime dependency installation failed with exit code $LASTEXITCODE." }

Write-Host 'Runtime installation complete.'
& $Python -c "import sys, tkinter, torch; print(sys.version); print('Tk', tkinter.TkVersion); print('Torch', torch.__version__, 'CUDA', torch.version.cuda)"
if ($LASTEXITCODE -ne 0) { throw "Runtime self-check failed with exit code $LASTEXITCODE." }
