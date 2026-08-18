@echo off
setlocal
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-update.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Update failed. The previous code was restored when replacement had started.
)
if not "%SEEDVR2_RELEASE_TEST%"=="1" pause
exit /b %EXIT_CODE%
