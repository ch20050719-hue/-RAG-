@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 (
  echo Run this script from an MSVC developer command prompt.
  exit /b 1
)

set "OUT_DIR=%TEMP%\mg90s_logic_test"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
pushd "%OUT_DIR%"
cl /nologo /std:c11 /W4 /WX /I"%~dp0..\HARDWARE\Servo" "%~dp0test_mg90s_logic.c" "%~dp0..\HARDWARE\Servo\MG90S_logic.c" /Fe:mg90s_logic_test.exe
if errorlevel 1 (
  popd
  exit /b 1
)
mg90s_logic_test.exe
set "TEST_RESULT=%ERRORLEVEL%"
popd
exit /b %TEST_RESULT%
