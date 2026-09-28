@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 (
  echo Run this script from an MSVC developer command prompt.
  exit /b 1
)

set "OUT_DIR=%TEMP%\threshold_step_test"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
pushd "%OUT_DIR%"
cl /nologo /std:c11 /W4 /WX /I"%~dp0..\USER" "%~dp0test_threshold_step.c" /Fe:threshold_step_test.exe
if errorlevel 1 (
  popd
  exit /b 1
)
threshold_step_test.exe
set "TEST_RESULT=%ERRORLEVEL%"
popd
exit /b %TEST_RESULT%
