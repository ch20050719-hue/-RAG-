@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 exit /b 1
set "TEST_DIR=%~dp0"
set "OUT_DIR=%TEMP%\stm32-ui-refresh-tests"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
pushd "%OUT_DIR%"
cl /nologo /std:c11 /W4 /WX "%TEST_DIR%test_ui_refresh.c" /Fe:ui_refresh_test.exe
if errorlevel 1 goto failed
ui_refresh_test.exe
if errorlevel 1 goto failed
popd
exit /b 0
:failed
popd
exit /b 1
