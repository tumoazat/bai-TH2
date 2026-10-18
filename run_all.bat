@echo off
setlocal
cd /d "%~dp0"
python run_all.py %*
if errorlevel 1 exit /b %errorlevel%
