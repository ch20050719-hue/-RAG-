@echo off
setlocal
cd /d "%~dp0"
if "%ARMCLANG_BIN%"=="" (
  echo Set ARMCLANG_BIN to the installed Arm Compiler 6.7 bin directory.
  exit /b 1
)
if not exist build mkdir build
for %%f in (axf hex bin) do if exist build\servo_door.%%f del /q build\servo_door.%%f
for %%f in (startup main board protocol) do (
  "%ARMCLANG_BIN%\armclang.exe" --target=arm-arm-none-eabi -mcpu=cortex-m3 -mthumb -std=c11 -Os -g -ffreestanding -fno-builtin -Wall -Wextra -Werror -D__MICROLIB -I. -c %%f.c -o build\%%f.o
  if errorlevel 1 exit /b 1
)
"%ARMCLANG_BIN%\armlink.exe" --cpu=Cortex-M3 --library_type=microlib --scatter=servo_door.sct --entry=Reset_Handler --keep=startup.o(RESET) --map --list=build\servo_door.map build\startup.o build\main.o build\board.o build\protocol.o --output=build\servo_door.axf
if errorlevel 1 exit /b 1
"%ARMCLANG_BIN%\fromelf.exe" --i32combined --output=build\servo_door.hex build\servo_door.axf
if errorlevel 1 exit /b 1
if not exist build\servo_door.hex exit /b 1
"%ARMCLANG_BIN%\fromelf.exe" --bin --output=build\servo_door.bin build\servo_door.axf
if errorlevel 1 exit /b 1
if not exist build\servo_door.bin exit /b 1
for %%I in (build\servo_door.bin) do if %%~zI GTR 65536 exit /b 1
exit /b %errorlevel%
