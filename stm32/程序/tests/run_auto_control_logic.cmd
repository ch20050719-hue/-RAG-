@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 exit /b 1
set "TEST_DIR=%~dp0"
set "OUT_DIR=%TEMP%\auto_control_logic_test"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
pushd "%OUT_DIR%"
cl /nologo /std:c11 /W4 /WX /I"%TEST_DIR%..\SYSTEM\TIM2" "%TEST_DIR%test_auto_control_logic.c" /Fe:auto_control_logic_test.exe
if errorlevel 1 (
  popd
  exit /b 1
)
auto_control_logic_test.exe
set "TEST_RESULT=%ERRORLEVEL%"
popd
exit /b %TEST_RESULT%
