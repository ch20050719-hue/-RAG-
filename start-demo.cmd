@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-demo.ps1" %*
if errorlevel 1 (
  echo.
  echo Launcher failed. Check the error message above.
  pause
)
