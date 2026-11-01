@echo off
setlocal
cd /d "%~dp0.."
if not exist build mkdir build
where cl >nul 2>nul
if errorlevel 1 (
  echo Run from an x64 Native Tools Command Prompt, or call vcvars64.bat first.
  exit /b 1
)
cl /nologo /W4 /WX /std:c11 /I. tests\test_protocol.c protocol.c /Febuild\test_protocol.exe /Fobuild\
if errorlevel 1 exit /b 1
build\test_protocol.exe
exit /b %errorlevel%
