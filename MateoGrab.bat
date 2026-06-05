@echo off
start "" pythonw "%~dp0server.py"
 
:wait
timeout /t 1 >nul
curl -s http://localhost:5000 >nul 2>&1
if errorlevel 1 goto wait
