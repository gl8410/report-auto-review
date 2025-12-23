@echo off
cd /d "%~dp0"
echo Activating virtual environment...
call venv\Scripts\activate
echo Starting Backend Server...
python run.py
pause
