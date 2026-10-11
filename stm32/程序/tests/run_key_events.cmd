@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 (
  echo Run this script from an MSVC developer command prompt.
  exit /b 1
)
set "OUT_DIR=%TEMP%\stm32-key-event-tests"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
pushd "%OUT_DIR%"
cl /nologo /W4 /WX "%~dp0test_key_events.c" /Fe:test_key_events.exe
if errorlevel 1 goto failed
test_key_events.exe
if errorlevel 1 goto failed
cl /nologo /W4 /WX /wd4819 /I"%~dp0key_stub" "%~dp0test_key_scan.c" "%~dp0..\HARDWARE\Key.c" /Fe:test_key_scan.exe
if errorlevel 1 goto failed
test_key_scan.exe
if errorlevel 1 goto failed
popd
exit /b 0
:failed
popd
exit /b 1
