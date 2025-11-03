@echo off 
chcp 65001 >nul 
cd /d "%~dp0" 
if exist ".venv\Scripts\python.exe" (".venv\Scripts\python.exe" -m src.run_bot) else (python -m src.run_bot || py -3 -m src.run_bot) 
 
echo Press any key to close... 
pause 
