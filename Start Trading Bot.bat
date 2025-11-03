@echo off
chcp 65001 >nul

echo 🚀 Starting MT5 Forex Trading Bot (launcher)...

REM Ensure we are in the script directory
cd /d "%~dp0"

REM Create a temporary runner batch that will be launched in a NEW window.
REM This avoids quoting issues when using start/cmd and ensures the window stays open.
set "TMP_RUN=%~dp0\.run_temp.bat"
echo @echo off > "%TMP_RUN%"
echo chcp 65001 ^>nul >> "%TMP_RUN%"
echo cd /d "%%~dp0" >> "%TMP_RUN%"
echo if exist ".venv\Scripts\python.exe" (".venv\Scripts\python.exe" -m src.run_bot) else (python -m src.run_bot ^|^| py -3 -m src.run_bot) >> "%TMP_RUN%"
echo. >> "%TMP_RUN%"
echo echo Press any key to close... >> "%TMP_RUN%"
echo pause >> "%TMP_RUN%"

REM Launch the temporary runner in a new window and return immediately to Explorer
start "" "%TMP_RUN%"

REM Note: the temp file remains in repo root; you can remove it later if desired.
