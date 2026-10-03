@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 (
  echo Run this script from an MSVC developer command prompt.
  exit /b 1
)

set "OUT_DIR=%TEMP%\window_voice_test"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
pushd "%OUT_DIR%"
cl /nologo /std:c11 /W4 /WX /I"%~dp0..\HARDWARE" "%~dp0test_window_motion.c" "%~dp0..\HARDWARE\window_motion.c" /Fe:window_motion_test.exe
if errorlevel 1 goto fail
window_motion_test.exe
if errorlevel 1 goto fail

cl /nologo /std:c11 /W4 /WX /I"%~dp0..\SYSTEM\usart" "%~dp0test_voice_command.c" "%~dp0..\SYSTEM\usart\voice_command.c" /Fe:voice_command_test.exe
if errorlevel 1 goto fail
voice_command_test.exe
if errorlevel 1 goto fail

popd
exit /b 0

:fail
popd
exit /b 1
