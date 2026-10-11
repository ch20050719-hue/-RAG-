@echo off
setlocal
set "TEST_DIR=%~dp0"
for %%T in (gizwits_logic window_voice mg90s_logic threshold_step dht11 adcx auto_control_logic key_events ui_refresh) do (
  call "%TEST_DIR%run_%%T.cmd"
  if errorlevel 1 exit /b 1
)
echo All firmware logic tests passed.
exit /b 0
