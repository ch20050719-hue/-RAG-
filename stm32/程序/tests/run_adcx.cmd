@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 (
  echo Run this script from an MSVC developer command prompt.
  exit /b 1
)
set "OUT_DIR=%TEMP%\adcx_test"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
pushd "%OUT_DIR%"
cl /nologo /std:c11 /W4 /WX /I"%~dp0adc_stub" "%~dp0test_adcx.c" "%~dp0..\SYSTEM\ADCX\ADCX.c" /Fe:adcx_test.exe
if errorlevel 1 (
  popd
  exit /b 1
)
adcx_test.exe
set "TEST_RESULT=%ERRORLEVEL%"
popd
exit /b %TEST_RESULT%
