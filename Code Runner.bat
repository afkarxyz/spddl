@echo off
:start
cd /d %~dp0
echo.
for %%f in (*.py) do (
    python "%%f"
    goto end_loop
)
:end_loop
echo.
echo Press any key to run again...
pause >nul
goto start