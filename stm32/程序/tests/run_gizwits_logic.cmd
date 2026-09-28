@echo off
setlocal
where cl >nul 2>nul
if errorlevel 1 (
  echo Run this script from an MSVC developer command prompt.
  exit /b 1
)

set "OUT_DIR=%TEMP%\gizwits_logic_test"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
pushd "%OUT_DIR%"

cl /nologo /std:c11 /utf-8 /W3 /wd4005 /wd4389 /wd4127 /wd4047 /wd4024 /wd4244 /wd4100 /Gy /I"%~dp0stubs" /I"%~dp0..\Gizwits" /I"%~dp0..\Utils" "%~dp0test_gizwits_product.c" /Fe:gizwits_product_test.exe /link /OPT:REF
if errorlevel 1 goto fail
gizwits_product_test.exe
if errorlevel 1 goto fail

cl /nologo /std:c11 /utf-8 /W3 /wd4005 /wd4389 /wd4127 /wd4047 /wd4024 /wd4244 /wd4100 /Gy /I"%~dp0..\Gizwits" /I"%~dp0..\Utils" "%~dp0test_gizwits_protocol.c" /Fe:gizwits_protocol_test.exe /link /OPT:REF
if errorlevel 1 goto fail
gizwits_protocol_test.exe
if errorlevel 1 goto fail

popd
exit /b 0

:fail
popd
exit /b 1
